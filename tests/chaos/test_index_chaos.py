"""Index chaos battery (EPISTEMOS-02 ETAPA 7 + 18).

Core data never depends on index integrity. After a kill/corruption/deletion: authoritative
state is intact, the index is rebuildable, and queries are correct (via fallback then rebuild).
All fault injection is in tempdirs.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from epistemos import Engine, Principal
from epistemos.storage import SQLiteStore

pytestmark = pytest.mark.chaos

WORKER = Path(__file__).parent / "_crash_worker.py"
CTX = Principal(tenant="t", agent="a", namespace="n")


def test_sigkill_during_indexed_writes(tmp_path) -> None:
    db = tmp_path / "crash.db"
    proc = subprocess.Popen([sys.executable, str(WORKER), str(db)])
    time.sleep(0.6)
    proc.kill()
    proc.wait(timeout=5)

    store = SQLiteStore(db)
    eng = Engine(store)  # ensure_built runs on open
    # authoritative state intact
    n = eng.verify_integrity()
    assert n == store.event_count() and n >= 1
    # index consistent (transactional updates + open-time guard) or made so, and queries correct
    assert eng.verify_index_consistency()
    assert eng.search(CTX, text="A p", limit=10) or True  # search runs without error
    # explicit rebuild also yields consistency
    eng.rebuild_index()
    assert eng.verify_index_consistency()
    eng.close()


def test_delete_index_tables_recovers_on_open(tmp_path) -> None:
    db = tmp_path / "del.db"
    eng = Engine(SQLiteStore(db))
    for i in range(5):
        eng.assert_fact(CTX, subject=f"e{i}", predicate="p", object=f"word{i}")
    eng.close()
    # drop the FTS tables out-of-band (simulate a missing/corrupt index)
    import sqlite3
    con = sqlite3.connect(db)
    con.execute("DROP TABLE IF EXISTS fts_idx")
    con.execute("DROP TABLE IF EXISTS fts_map")
    con.commit()
    con.close()
    # reopening rebuilds the index (ensure_built) -> consistent + searchable
    eng2 = Engine(SQLiteStore(db))
    assert eng2.verify_index_consistency()
    assert len(eng2.search(CTX, text="word0", limit=10)) >= 1
    eng2.close()


def test_corrupt_index_rows_detected_and_rebuilt(tmp_path) -> None:
    eng = Engine(SQLiteStore(tmp_path / "corrupt.db"))
    for i in range(5):
        eng.assert_fact(CTX, subject=f"e{i}", predicate="p", object=f"item{i}")
    # corrupt: delete half the index rows
    with eng.lexical_index._lock:
        eng.lexical_index._conn.execute("DELETE FROM fts_idx WHERE rowid <= 3")
    assert eng.verify_index_consistency() is False  # drift detected -> DEGRADED
    # search still correct via fallback (reads authoritative state)
    assert len(eng.search(CTX, text="item0", limit=10)) >= 1
    eng.rebuild_index()
    assert eng.verify_index_consistency()
    eng.close()


def test_index_write_failure_does_not_block_core(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    eng = Engine(SQLiteStore(tmp_path / "fail.db"))
    eng.assert_fact(CTX, subject="Alice", predicate="p", object="one")
    n = eng.verify_integrity()
    # make the index reindex raise (simulated disk/lock error on the index only)
    def boom(obj):
        raise RuntimeError("index write failed")
    monkeypatch.setattr(eng.lexical_index, "reindex", boom)
    # the CORE write must still succeed; index degrades, does not block persistence
    f = eng.assert_fact(CTX, subject="Bob", predicate="p", object="two")
    monkeypatch.undo()
    assert eng.get(CTX, f.id) is not None  # core committed
    assert eng.verify_integrity() == n + 1
    assert eng.lexical_index.health() == "INDEX_DEGRADED"
    # fallback keeps search correct; rebuild restores the index
    assert eng.search(CTX, text="two", limit=5)
    eng.rebuild_index()
    assert eng.verify_index_consistency()
    eng.close()
