"""SQLite FTS5 lexical index (EPISTEMOS-02, ADR-017).

Lives in the **same SQLite database and connection** as :class:`~epistemos.storage.SQLiteStore`,
so index updates commit or roll back **in the same transaction** as the primary projection — the
index can never silently diverge from the authoritative state on a crash (transactional
consistency by construction). It indexes **all** object versions (historical + current); the
retriever applies temporal filtering over the small candidate set.

If the SQLite build lacks FTS5, the index reports ``UNAVAILABLE`` and the engine falls back to the
scan retriever (correct, slower). If a reindex fails mid-write, the failure is isolated so the core
commit still succeeds and the index is marked ``DEGRADED`` (rebuildable) — the core never depends on
index integrity (ADR-019).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from ..storage.sqlite import SQLiteStore
from . import IndexHealth, LexicalIndex
from .text import ASCII, Tokenizer, fts_match_query, object_text

__all__ = ["SqliteFtsIndex"]

# The FTS5 tokenizer is chosen at build time; the fts_map + rid mapping is tokenizer-independent.
_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts_idx USING fts5(
    content, obj_id UNINDEXED, tenant UNINDEXED, namespace UNINDEXED, kind UNINDEXED,
    tokenize = {tokenize!r}
);
CREATE TABLE IF NOT EXISTS fts_map (obj_id TEXT PRIMARY KEY, rid INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_fts_map_rid ON fts_map(rid);
"""


#: Text used to detect whether a tokenizer rewrites content before indexing. It contains a plural,
#: an accent and mixed case, so any of the transformations E-2 measured shows up in the result.
_PROBE = "Several audits were recorded in São Paulo"


class SqliteFtsIndex(LexicalIndex):
    def __init__(self, store: SQLiteStore, *, tokenizer: Tokenizer = ASCII) -> None:
        self._store = store
        self._conn = store._conn
        self._lock = store._lock
        self._tokenizer = tokenizer
        self._state = IndexHealth.HEALTHY
        try:
            with self._lock:
                self._conn.executescript(_SCHEMA.format(tokenize=tokenizer.fts_tokenize))
        except sqlite3.OperationalError as exc:
            # Only a genuinely absent FTS5 module (or unknown tokenizer) means UNAVAILABLE — a
            # permanent, no-index state. A transient error like "database is locked" must NOT be
            # misdiagnosed as "FTS5 not compiled in" and permanently disable the index (OV-03).
            msg = str(exc).lower()
            if "no such module" in msg or "no such tokenizer" in msg or "fts5" in msg:
                self._state = IndexHealth.UNAVAILABLE
            else:
                raise

    # -- mutation (called inside the store's transaction) --------------------
    def reindex(self, obj: dict[str, Any]) -> None:
        if self._state == IndexHealth.UNAVAILABLE:
            return
        try:
            with self._lock:
                self._remove_locked(obj["id"])
                text = self._indexed_text(obj)
                if not text:
                    return
                self._conn.execute(
                    "INSERT INTO fts_idx(content, obj_id, tenant, namespace, kind) "
                    "VALUES (?,?,?,?,?)",
                    (text, obj["id"], obj["tenant"], obj["namespace"], obj.get("kind")),
                )
                rid = self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                self._conn.execute(
                    "INSERT OR REPLACE INTO fts_map(obj_id, rid) VALUES (?,?)", (obj["id"], rid)
                )
        except sqlite3.Error:
            # isolate: the core write must still commit; mark index degraded (rebuildable)
            self._state = IndexHealth.DEGRADED

    def remove(self, obj_id: str) -> None:
        if self._state == IndexHealth.UNAVAILABLE:
            return
        try:
            with self._lock:
                self._remove_locked(obj_id)
        except sqlite3.Error:
            self._state = IndexHealth.DEGRADED

    def _remove_locked(self, obj_id: str) -> None:
        row = self._conn.execute("SELECT rid FROM fts_map WHERE obj_id = ?", (obj_id,)).fetchone()
        if row is not None:
            self._conn.execute("DELETE FROM fts_idx WHERE rowid = ?", (row[0],))
            self._conn.execute("DELETE FROM fts_map WHERE obj_id = ?", (obj_id,))

    def clear(self) -> None:
        if self._state == IndexHealth.UNAVAILABLE:
            return
        with self._lock:
            self._conn.execute("DELETE FROM fts_idx")
            self._conn.execute("DELETE FROM fts_map")

    # -- query ---------------------------------------------------------------
    def search(
        self,
        tenant: str,
        namespace: str,
        text: str,
        *,
        kinds: tuple[str, ...] | None = None,
        limit: int = 500,
    ) -> list[tuple[str, float]]:
        if self._state != IndexHealth.HEALTHY:
            raise RuntimeError(f"index not healthy: {self._state}")
        match = fts_match_query(text, self._tokenizer)
        if match is None:
            return []
        sql = (
            "SELECT obj_id, bm25(fts_idx) AS score FROM fts_idx "
            "WHERE fts_idx MATCH ? AND tenant = ? AND namespace = ?"
        )
        params: list[Any] = [match, tenant, namespace]
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            sql += f" AND kind IN ({placeholders})"
            params.extend(kinds)
        sql += " ORDER BY score LIMIT ?"
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        if not rows:
            return []
        # bm25 is negative (more negative = more relevant); normalize to (0,1] over the result set
        rels = [(-float(r[1])) for r in rows]
        max_rel = max(rels) or 1.0
        return [(rows[i][0], min(1.0, rels[i] / max_rel)) for i in range(len(rows))]

    # -- health / maintenance ------------------------------------------------
    def count(self) -> int:
        if self._state == IndexHealth.UNAVAILABLE:
            return 0
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM fts_map").fetchone()[0])

    def health(self) -> IndexHealth:
        return self._state

    def ensure_built(self, store: Any = None) -> None:
        """Cheap open-time guard: rebuild once if the index does not match current state.

        Rebuilds when the object count and index count disagree (opening a pre-existing/v0.1
        database) OR when the persisted tokenizer differs from the requested one (the FTS5
        table's ``tokenize=`` is fixed at CREATE, so a tokenizer change means drop + rebuild
        with the new virtual table — ADR-023). The tokenizer name is recorded in ``meta``.
        """
        if self._state == IndexHealth.UNAVAILABLE:
            return
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = 'fts_tokenizer'"
            ).fetchone()
            stored = row[0] if row is not None else None
            obj_count = int(self._conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0])
        if stored != self._tokenizer.name:
            # A tokenizer change is a change of *persisted representation* (E-3), so the old
            # index is not merely stale, it is written in a different language. Drop it whole and
            # rebuild: a partially-migrated index would answer some queries in the old
            # representation and some in the new, which is worse than no index at all.
            self._recreate_table()
            self.rebuild(store)
            if not self.verify(store):
                # Fail closed. The rebuild produced something that does not match the
                # authoritative objects, so the index must not be trusted or recorded as
                # migrated: leave it DEGRADED and let the engine fall back to the scan path,
                # which is correct and merely slower. Recording the new tokenizer name here
                # would make the next open believe the migration succeeded.
                self.mark_degraded()
                return
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES ('fts_tokenizer', ?)",
                    (self._tokenizer.name,),
                )
        elif obj_count != self.count():
            # Cheap check disagreed — but objects with no searchable text (e.g. an empty
            # observation) are legitimately unindexed, so obj_count > index count is expected.
            # Only rebuild if the *searchable* set really differs, so a single empty object does
            # not force a full rebuild on every open (B-06).
            if len(self._searchable_ids()) != self.count():
                self.rebuild(store)

    def _recreate_table(self) -> None:
        """Drop and recreate the FTS5 virtual table with the current tokenizer."""
        with self._lock:
            self._conn.execute("DROP TABLE IF EXISTS fts_idx")
            self._conn.execute("DELETE FROM fts_map")
            self._conn.executescript(_SCHEMA.format(tokenize=self._tokenizer.fts_tokenize))

    def mark_degraded(self) -> None:
        if self._state != IndexHealth.UNAVAILABLE:
            self._state = IndexHealth.DEGRADED

    def restore_healthy(self) -> None:
        """Return a DEGRADED index to HEALTHY after it has been rebuilt from authoritative state.
        A no-op if the backend is UNAVAILABLE (there is nothing to be healthy about)."""
        if self._state != IndexHealth.UNAVAILABLE:
            self._state = IndexHealth.HEALTHY

    def _indexed_text(self, obj: dict[str, Any]) -> str:
        """The exact bytes stored in the FTS content cell.

        This is the persisted *representation*, not the object's text. SQLite tokenizes what is
        stored here, so normalising before the insert is what keeps the index in agreement with a
        query normalised by the same tokenizer (E-3). For a tokenizer whose ``normalize_text`` is
        identity — every tokenizer shipped before E-3 — this is byte-for-byte the old behaviour.
        """
        text = object_text(obj)
        return self._tokenizer.normalize_text(text) if text else text

    def _searchable_ids(self) -> set[str]:
        import json

        ids = set()
        with self._lock:
            rows = self._conn.execute("SELECT json FROM objects").fetchall()
        for (blob,) in rows:
            obj = json.loads(blob)
            if self._indexed_text(obj):
                ids.add(obj["id"])
        return ids

    def verify_detail(self, store: Any = None) -> dict[str, Any]:
        """Verify the index and report *what* was compared, not just whether it agreed.

        A boolean says the index is consistent; it does not say consistent *with what*. Since E-3
        the indexed content is a normalised representation rather than the object's text, so a
        reader has to be able to see all four layers to trust the answer (mission E-3 §5):

        ``original`` the object's searchable text · ``normalized`` what the tokenizer says should
        be stored · ``indexed`` what is actually in the FTS content cell · ``tokens`` how the
        stored form tokenizes. When ``ok`` is false, ``divergences`` names the first offenders
        rather than making the caller diff two databases by hand.
        """
        import json

        if self._state == IndexHealth.UNAVAILABLE:
            return {"ok": False, "reason": "index unavailable", "checked": 0, "divergences": []}
        with self._lock:
            mapping = {r[0]: r[1] for r in
                       self._conn.execute("SELECT obj_id, rid FROM fts_map").fetchall()}
            content = {r[0]: r[1] for r in
                       self._conn.execute("SELECT rowid, content FROM fts_idx").fetchall()}
            rows = self._conn.execute("SELECT json FROM objects").fetchall()

        divergences: list[dict[str, Any]] = []
        expected: dict[str, dict[str, Any]] = {}
        for (blob,) in rows:
            obj = json.loads(blob)
            original = object_text(obj)
            if not original:
                continue
            expected[obj["id"]] = {
                "original": original,
                "normalized": self._tokenizer.normalize_text(original),
            }

        missing = sorted(set(expected) - set(mapping))
        extra = sorted(set(mapping) - set(expected))
        for obj_id in missing[:5]:
            divergences.append({"obj_id": obj_id, "problem": "indexed=absent",
                                **expected[obj_id]})
        for obj_id in extra[:5]:
            divergences.append({"obj_id": obj_id, "problem": "indexed=orphan"})

        for obj_id, rid in mapping.items():
            if obj_id not in expected:
                continue
            want = expected[obj_id]["normalized"]
            got = content.get(rid)
            if got != want and len(divergences) < 10:
                divergences.append({
                    "obj_id": obj_id, "problem": "content drift",
                    "original": expected[obj_id]["original"][:120],
                    "normalized": want[:120],
                    "indexed": (got or "")[:120],
                    "tokens_expected": self._tokenizer.tokens(want)[:12],
                    "tokens_indexed": self._tokenizer.tokens(got or "")[:12],
                })

        ok = not missing and not extra and not any(
            d["problem"] == "content drift" for d in divergences)
        if not ok and self._state == IndexHealth.HEALTHY:
            self._state = IndexHealth.DEGRADED
        return {
            "ok": ok,
            "checked": len(expected),
            "indexed": len(mapping),
            "tokenizer": self._tokenizer.name,
            # Probe with words the transformation would actually touch; "x y" is unchanged by
            # every conservative rule and would report identity for a tokenizer that normalises.
            "representation": ("identity" if self._tokenizer.normalize_text(_PROBE) == _PROBE
                               else "normalized"),
            "divergences": divergences,
        }

    def verify(self, store: Any = None) -> bool:
        if self._state == IndexHealth.UNAVAILABLE:
            return False
        import json

        with self._lock:
            mapping = {
                r[0]: r[1]
                for r in self._conn.execute("SELECT obj_id, rid FROM fts_map").fetchall()
            }
            map_count = int(self._conn.execute("SELECT COUNT(*) FROM fts_map").fetchone()[0])
            idx_count = int(self._conn.execute("SELECT COUNT(*) FROM fts_idx").fetchone()[0])
            content = {
                r[0]: r[1]
                for r in self._conn.execute("SELECT rowid, content FROM fts_idx").fetchall()
            }
            rows = self._conn.execute("SELECT json FROM objects").fetchall()
        # 1. mapping drift: the indexed id set must equal the authoritative searchable set, and
        #    the map/idx row counts must agree.
        searchable = {}
        for (blob,) in rows:
            obj = json.loads(blob)
            text = self._indexed_text(obj)
            if text:
                searchable[obj["id"]] = text
        ok = (set(mapping) == set(searchable)) and (map_count == idx_count)
        # 2. content drift: each mapped row's indexed content must still equal the object's text.
        #    Catches a corrupted/rewritten content cell that leaves the mapping intact (B-01).
        if ok:
            for obj_id, rid in mapping.items():
                if content.get(rid) != searchable.get(obj_id):
                    ok = False
                    break
        if not ok and self._state == IndexHealth.HEALTHY:
            self._state = IndexHealth.DEGRADED
        return ok

    def rebuild(self, store: Any = None) -> int:
        if self._state == IndexHealth.UNAVAILABLE:
            return 0
        import json

        self._state = IndexHealth.REBUILDING
        try:
            with self._store.atomic():
                self.clear()
                with self._lock:
                    rows = self._conn.execute("SELECT json FROM objects").fetchall()
                for (blob,) in rows:
                    self._reindex_healthy(json.loads(blob))
            self._state = IndexHealth.HEALTHY
            return self.count()
        except sqlite3.Error:
            self._state = IndexHealth.DEGRADED
            raise

    def _reindex_healthy(self, obj: dict[str, Any]) -> None:
        """Reindex that raises on error (used by rebuild, which owns the transaction)."""
        self._remove_locked(obj["id"])
        text = self._indexed_text(obj)
        if not text:
            return
        with self._lock:
            self._conn.execute(
                "INSERT INTO fts_idx(content, obj_id, tenant, namespace, kind) VALUES (?,?,?,?,?)",
                (text, obj["id"], obj["tenant"], obj["namespace"], obj.get("kind")),
            )
            rid = self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            self._conn.execute(
                "INSERT OR REPLACE INTO fts_map(obj_id, rid) VALUES (?,?)", (obj["id"], rid)
            )
