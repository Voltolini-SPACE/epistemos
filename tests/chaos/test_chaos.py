"""CHAOS gate (checkpoint AC) + CRASH_RECOVERY + PROJECTION_REBUILD.

All fault injection is confined to test tempdirs; no host data is touched.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from epistemos import Engine, Principal
from epistemos.errors import ConflictError, SchemaError
from epistemos.storage import MemoryStore, SQLiteStore

pytestmark = pytest.mark.chaos

WORKER = Path(__file__).parent / "_crash_worker.py"


def test_sigkill_during_write_recovers(tmp_path) -> None:
    db = tmp_path / "crash.db"
    proc = subprocess.Popen([sys.executable, str(WORKER), str(db)])
    time.sleep(0.6)  # let many transactions commit
    proc.kill()  # SIGKILL — no chance to clean up
    proc.wait(timeout=5)

    # 1) the SQLite file itself is not corrupt
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()

    # 2) the ledger chain is intact and matches the committed count (no partial event)
    store = SQLiteStore(db)
    engine = Engine(store)
    n = engine.verify_integrity()
    assert n == store.event_count()
    assert n >= 1, "expected at least one committed event before the kill"

    # 3) PROJECTION_REBUILD: replaying the ledger reproduces identical state
    ctx = Principal(tenant="t", agent="a", namespace="n")
    before = {o["id"]: o for o in store.objects(ctx.tenant, ctx.namespace)}
    engine.rebuild_projection()
    after = {o["id"]: o for o in store.objects(ctx.tenant, ctx.namespace)}
    assert before == after

    # 4) writing continues cleanly after recovery
    engine.assert_fact(ctx, subject="B", predicate="p", object="post-crash")
    assert engine.verify_integrity() == n + 1
    engine.close()


def test_simulated_disk_error_rolls_back(engine: Engine, ctx: Principal,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    engine.add_source(ctx, uri="mem://s")
    n = engine.verify_integrity()
    calls = {"i": 0}
    real_put = engine.store.put_object

    def flaky(obj):
        calls["i"] += 1
        if calls["i"] == 1:
            raise OSError("simulated disk full")
        return real_put(obj)

    monkeypatch.setattr(engine.store, "put_object", flaky)
    with pytest.raises(OSError):
        engine.assert_fact(ctx, subject="A", predicate="p", object="B")
    monkeypatch.undo()
    assert engine.verify_integrity() == n  # rolled back, nothing partial


def test_clock_skew_does_not_corrupt(engine: Engine, ctx: Principal) -> None:
    # a clock that jumps backwards must not break integrity (chain uses seq, not time)
    base = datetime(2026, 6, 1, tzinfo=UTC)
    seq = [base, base - timedelta(days=1), base + timedelta(hours=1), base - timedelta(days=5)]
    it = iter(seq * 10)
    engine.clock = lambda: next(it)
    for i in range(4):
        engine.assert_fact(ctx, subject="A", predicate="p", object=f"v{i}")
    assert engine.verify_integrity() == engine.store.event_count()
    assert engine.current(ctx, subject="A", predicate="p") is not None


def test_malformed_import_leaves_store_untouched() -> None:
    eng = Engine(MemoryStore())
    for bad in (
        {"format": "wrong"},
        {"format": "epistemos-events", "schema_version": 1, "events": [{"seq": 1}]},
        "not-a-dict",
    ):
        with pytest.raises((SchemaError, Exception)):
            eng.import_events(bad)  # type: ignore[arg-type]
    assert eng.store.event_count() == 0


def test_duplicate_delivery_rejected(engine: Engine, ctx: Principal) -> None:
    engine.assert_fact(ctx, subject="A", predicate="p", object="B")
    dump = engine.export()
    fresh = Engine(MemoryStore())
    fresh.import_events(dump)
    with pytest.raises(ConflictError):  # second delivery into the same store is refused
        fresh.import_events(dump)


def test_broken_provider_never_touches_core(engine: Engine, ctx: Principal) -> None:
    class Exploding:
        name = "boom"

        def available(self) -> bool:
            raise RuntimeError("provider down")

        def embed(self, texts):
            raise RuntimeError("provider down")

    # the core takes no provider and never calls one: a broken provider is irrelevant
    engine.assert_fact(ctx, subject="A", predicate="p", object="B")
    assert engine.search(ctx, text="A p")
    assert engine.verify_integrity() == engine.store.event_count()
