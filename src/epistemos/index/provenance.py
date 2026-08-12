"""Provenance activity index (EPISTEMOS-03, ADR-022).

``explain(id)`` answers *what happened to this object* by listing the ledger events (PROV
activities) whose payload references it. v0.2 answered that by scanning the **entire** ledger
once per node of the genealogy tree, so the cost of explaining one fact grew with the size of
the whole history — measured at 14.5 ms / 158 ms / **1926 ms** for 1k / 10k / 100k events.

This module inverts that scan into a rebuildable projection: ``obj_id -> [seq, …]``. It follows
exactly the :mod:`epistemos.index.fts` contract, for the same reasons (ADR-018/019):

* it lives in the **same SQLite database and connection** as the store, so an index write
  commits or rolls back in the same transaction as the authoritative write;
* it is a **projection, never a source of truth** — it is rebuilt from the ledger, and every
  query it serves must be answerable without it;
* it reports :class:`~epistemos.index.IndexHealth` so a caller falls back to the authoritative
  scan rather than returning an incomplete genealogy.

Only *id-shaped* string leaves are indexed (``prefix_<32 hex>``, the shape
:func:`epistemos._util.new_id` produces). The scan it replaces matches an id anywhere it occurs
as a string **value**, so indexing that shape is exact for any id the engine minted. An object
whose id does not have that shape — a hand-authored id in an imported export, say — is served by
the scan instead, which is why :meth:`SqliteProvenanceIndex.is_indexable` gates every lookup.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from ..storage.sqlite import SQLiteStore
from . import IndexHealth

__all__ = ["SqliteProvenanceIndex", "ID_SHAPE"]

# The shape epistemos._util.new_id() mints: a lowercase type prefix + uuid4().hex.
ID_SHAPE = re.compile(r"^[a-z]+_[0-9a-f]{32}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prov_ref (
    obj_id TEXT NOT NULL,
    seq    INTEGER NOT NULL,
    PRIMARY KEY (obj_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_prov_ref_obj ON prov_ref(obj_id);
-- The idempotency DELETE in record() keys on seq. Without this index it degrades to a full
-- scan per event, which made rebuild_projection O(events^2): measured 4.5s -> 270s at 100k.
CREATE INDEX IF NOT EXISTS idx_prov_ref_seq ON prov_ref(seq);
"""


def id_leaves(value: Any, out: set[str]) -> set[str]:
    """Collect every id-shaped string leaf in ``value``."""
    if isinstance(value, str):
        if ID_SHAPE.match(value):
            out.add(value)
    elif isinstance(value, dict):
        for v in value.values():
            id_leaves(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            id_leaves(v, out)
    return out


class SqliteProvenanceIndex:
    """Maps an object id to the ledger sequence numbers whose payload references it."""

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store
        self._conn = store._conn
        self._lock = store._lock
        self._state = IndexHealth.HEALTHY
        try:
            with self._lock:
                self._conn.executescript(_SCHEMA)
        except sqlite3.OperationalError:  # pragma: no cover - defensive
            self._state = IndexHealth.UNAVAILABLE

    # -- mutation (inside the store's transaction) ---------------------------
    def record(self, seq: int, payload: Any) -> None:
        """Index one sealed record. Idempotent for a given ``seq``."""
        if self._state == IndexHealth.UNAVAILABLE:
            return
        try:
            with self._lock:
                self._conn.execute("DELETE FROM prov_ref WHERE seq = ?", (seq,))
                refs = id_leaves(payload, set())
                if refs:
                    self._conn.executemany(
                        "INSERT OR REPLACE INTO prov_ref(obj_id, seq) VALUES (?,?)",
                        [(r, seq) for r in refs],
                    )
        except sqlite3.Error:
            # isolate: the authoritative write must still commit (ADR-019)
            self._state = IndexHealth.DEGRADED

    def clear(self) -> None:
        if self._state == IndexHealth.UNAVAILABLE:
            return
        with self._lock:
            self._conn.execute("DELETE FROM prov_ref")

    # -- query ---------------------------------------------------------------
    def is_indexable(self, obj_id: str) -> bool:
        """Can this id be answered from the index with the same result as a scan?"""
        return bool(ID_SHAPE.match(obj_id))

    def usable_for(self, obj_id: str) -> bool:
        return self._state == IndexHealth.HEALTHY and self.is_indexable(obj_id)

    def seqs_for(self, obj_id: str) -> list[int]:
        """Ledger sequence numbers referencing ``obj_id``, ascending."""
        if not self.usable_for(obj_id):
            raise RuntimeError(f"provenance index not usable for {obj_id!r}: {self._state}")
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq FROM prov_ref WHERE obj_id = ? ORDER BY seq", (obj_id,)
            ).fetchall()
        return [int(r[0]) for r in rows]

    # -- health / maintenance ------------------------------------------------
    def count(self) -> int:
        if self._state == IndexHealth.UNAVAILABLE:
            return 0
        with self._lock:
            return int(
                self._conn.execute("SELECT COUNT(DISTINCT seq) FROM prov_ref").fetchone()[0]
            )

    def health(self) -> IndexHealth:
        return self._state

    def mark_degraded(self) -> None:
        if self._state != IndexHealth.UNAVAILABLE:
            self._state = IndexHealth.DEGRADED

    def ensure_built(self) -> None:
        """Rebuild once if the index does not cover every referencing event (e.g. opening a
        v0.1/v0.2 database that predates this index)."""
        if self._state == IndexHealth.UNAVAILABLE:
            return
        if self._expected_seq_count() != self.count():
            self.rebuild()

    def _expected_seq_count(self) -> int:
        """How many ledger events reference at least one id-shaped value."""
        import json

        with self._lock:
            rows = self._conn.execute("SELECT seq, payload_json FROM ledger").fetchall()
        return sum(1 for _, blob in rows if id_leaves(json.loads(blob), set()))

    def verify(self, store: Any = None) -> bool:
        """True iff the index reproduces exactly what a ledger scan would find."""
        if self._state == IndexHealth.UNAVAILABLE:
            return False
        import json

        with self._lock:
            rows = self._conn.execute("SELECT seq, payload_json FROM ledger").fetchall()
            indexed = {
                (r[0], int(r[1]))
                for r in self._conn.execute("SELECT obj_id, seq FROM prov_ref").fetchall()
            }
        expected: set[tuple[str, int]] = set()
        for seq, blob in rows:
            for ref in id_leaves(json.loads(blob), set()):
                expected.add((ref, int(seq)))
        ok = indexed == expected
        if not ok and self._state == IndexHealth.HEALTHY:
            self._state = IndexHealth.DEGRADED
        return ok

    def rebuild(self, store: Any = None) -> int:
        """Drop and rebuild from the authoritative ledger. Returns events indexed."""
        if self._state == IndexHealth.UNAVAILABLE:
            return 0
        import json

        self._state = IndexHealth.REBUILDING
        try:
            with self._store.atomic():
                self.clear()
                with self._lock:
                    rows = self._conn.execute("SELECT seq, payload_json FROM ledger").fetchall()
                for seq, blob in rows:
                    refs = id_leaves(json.loads(blob), set())
                    if refs:
                        with self._lock:
                            self._conn.executemany(
                                "INSERT OR REPLACE INTO prov_ref(obj_id, seq) VALUES (?,?)",
                                [(r, int(seq)) for r in refs],
                            )
            self._state = IndexHealth.HEALTHY
            return self.count()
        except sqlite3.Error:
            self._state = IndexHealth.DEGRADED
            raise
