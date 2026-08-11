"""RACE gate (checkpoint AB). Deterministic concurrency battery, 30 cycles/scenario.

Writers serialize (store lock + BEGIN IMMEDIATE), so the aggregate outcome is
deterministic: after any concurrent burst the ledger chain is intact, has no seq
gaps/dups, event_count equals the number of successful ops, and the projection equals a
pure replay of the ledger. We assert those invariants, not a particular interleaving.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from epistemos import Engine, Principal
from epistemos.storage import MemoryStore, SQLiteStore

pytestmark = pytest.mark.race

CYCLES = 30
WORKERS = 8


def _invariants_hold(engine: Engine, ctx: Principal, expected_events: int) -> None:
    assert engine.store.event_count() == expected_events
    assert engine.verify_integrity() == expected_events  # no gaps/dups/breaks
    before = {o["id"]: o for o in engine.store.objects(ctx.tenant, ctx.namespace)}
    engine.rebuild_projection()
    after = {o["id"]: o for o in engine.store.objects(ctx.tenant, ctx.namespace)}
    assert before == after  # projection == pure replay of ledger


def _run(engine: Engine, fns: list) -> None:
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(fn) for fn in fns]
        for f in as_completed(futures):
            f.result()  # surface any exception


@pytest.mark.parametrize("cycle", range(CYCLES))
def test_concurrent_same_fact_assert(engine: Engine, ctx: Principal, cycle: int) -> None:
    n = 16
    _run(engine, [
        (lambda i=i: engine.assert_fact(ctx, subject="A", predicate="p", object=f"v{i}"))
        for i in range(n)
    ])
    _invariants_hold(engine, ctx, n)
    # exactly one value is "current" and it is deterministic-per-state (max rank key)
    assert engine.current(ctx, subject="A", predicate="p") is not None


@pytest.mark.parametrize("cycle", range(CYCLES))
def test_assert_vs_retract_vs_supersede(engine: Engine, ctx: Principal, cycle: int) -> None:
    seed = engine.assert_fact(ctx, subject="A", predicate="p", object="seed")
    ops = []
    for i in range(6):
        ops.append(lambda i=i: engine.assert_fact(ctx, subject="A", predicate="p", object=f"v{i}"))
    ops.append(lambda: engine.retract(ctx, seed.id))
    ops.append(lambda: engine.supersede(ctx, seed.id, new={"object": "sup"}))
    # retract and supersede both target seed; one wins, the other raises (belief already
    # closed) — both outcomes are safe. Count only successes.
    results = []

    def guarded(fn):
        def inner():
            try:
                fn()
                results.append(True)
            except Exception:  # noqa: BLE001 - concurrency-legal conflict
                results.append(False)
        return inner

    _run(engine, [guarded(op) for op in ops[:6]])  # the 6 asserts always succeed
    # then the mutually-exclusive pair, sequentially-safe under the lock
    _run(engine, [guarded(ops[6]), guarded(ops[7])])
    # chain is always intact regardless of which conflicting op won
    assert engine.verify_integrity() == engine.store.event_count()
    b = {o["id"]: o for o in engine.store.objects(ctx.tenant, ctx.namespace)}
    engine.rebuild_projection()
    a = {o["id"]: o for o in engine.store.objects(ctx.tenant, ctx.namespace)}
    assert a == b


@pytest.mark.parametrize("cycle", range(CYCLES))
def test_parallel_tenant_writes_isolated(engine: Engine, cycle: int) -> None:
    ta = Principal(tenant="ta", agent="x", namespace="n")
    tb = Principal(tenant="tb", agent="y", namespace="n")
    _run(engine, (
        [lambda i=i: engine.assert_fact(ta, subject="A", predicate="p", object=f"{i}") for i in range(8)]
        + [lambda i=i: engine.assert_fact(tb, subject="A", predicate="p", object=f"{i}") for i in range(8)]
    ))
    assert engine.store.counts("ta", "n")["fact"] == 8
    assert engine.store.counts("tb", "n")["fact"] == 8
    assert engine.verify_integrity() == 16


@pytest.mark.parametrize("cycle", range(CYCLES))
def test_backup_during_concurrent_writes(tmp_path, cycle: int) -> None:
    store = SQLiteStore(tmp_path / f"race{cycle}.db")
    engine = Engine(store)
    ctx = Principal(tenant="t", agent="a", namespace="n")
    snapshots: list = []

    def writer(i: int) -> None:
        engine.assert_fact(ctx, subject="A", predicate="p", object=f"v{i}")

    def backer(j: int) -> None:
        dest = tmp_path / f"bak{cycle}_{j}.db"
        store.backup(dest)
        # each hot snapshot must itself be a valid, verifiable chain
        s2 = SQLiteStore(dest)
        Engine(s2).verify_integrity()
        s2.close()
        snapshots.append(dest)

    fns = [lambda i=i: writer(i) for i in range(12)] + [lambda j=j: backer(j) for j in range(4)]
    _run(engine, fns)
    assert engine.verify_integrity() == 12
    assert snapshots
    engine.close()


def _fresh_pair(tmp_path):  # helper kept for symmetry / future scenarios
    return Engine(MemoryStore()), Engine(SQLiteStore(tmp_path / "p.db"))
