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
from .text import fts_match_query, object_text

__all__ = ["SqliteFtsIndex"]

_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts_idx USING fts5(
    content, obj_id UNINDEXED, tenant UNINDEXED, namespace UNINDEXED, kind UNINDEXED,
    tokenize = 'ascii'
);
CREATE TABLE IF NOT EXISTS fts_map (obj_id TEXT PRIMARY KEY, rid INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_fts_map_rid ON fts_map(rid);
"""


class SqliteFtsIndex(LexicalIndex):
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store
        self._conn = store._conn
        self._lock = store._lock
        self._state = IndexHealth.HEALTHY
        try:
            with self._lock:
                self._conn.executescript(_SCHEMA)
        except sqlite3.OperationalError:
            # FTS5 not compiled into this SQLite build
            self._state = IndexHealth.UNAVAILABLE

    # -- mutation (called inside the store's transaction) --------------------
    def reindex(self, obj: dict[str, Any]) -> None:
        if self._state == IndexHealth.UNAVAILABLE:
            return
        try:
            with self._lock:
                self._remove_locked(obj["id"])
                text = object_text(obj)
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
        match = fts_match_query(text)
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
        """Cheap open-time guard: if the object count and index count disagree (e.g. opening a
        pre-existing or v0.1 database), rebuild once so search is complete and HEALTHY."""
        if self._state == IndexHealth.UNAVAILABLE:
            return
        with self._lock:
            obj_count = int(self._conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0])
        if obj_count != self.count():
            self.rebuild(store)

    def mark_degraded(self) -> None:
        if self._state != IndexHealth.UNAVAILABLE:
            self._state = IndexHealth.DEGRADED

    def _searchable_ids(self) -> set[str]:
        import json

        ids = set()
        with self._lock:
            rows = self._conn.execute("SELECT json FROM objects").fetchall()
        for (blob,) in rows:
            obj = json.loads(blob)
            if object_text(obj):
                ids.add(obj["id"])
        return ids

    def verify(self, store: Any = None) -> bool:
        if self._state == IndexHealth.UNAVAILABLE:
            return False
        with self._lock:
            indexed = {r[0] for r in self._conn.execute("SELECT obj_id FROM fts_map").fetchall()}
            map_count = int(self._conn.execute("SELECT COUNT(*) FROM fts_map").fetchone()[0])
            idx_count = int(self._conn.execute("SELECT COUNT(*) FROM fts_idx").fetchone()[0])
        # detect both mapping drift (fts_map vs authoritative) and content drift (fts_idx rows
        # deleted/corrupted while the mapping remains)
        ok = (indexed == self._searchable_ids()) and (map_count == idx_count)
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
        text = object_text(obj)
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
