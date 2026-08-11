"""Index race battery (EPISTEMOS-02 ETAPA 17), 30 cycles/scenario.

Writers, searchers, rebuilds and backups run concurrently on the FTS-backed engine. Invariant
after any burst: the ledger chain verifies, the index is consistent with authoritative state, and
searches return correct (never stale/partial) results.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from epistemos import Engine, Principal
from epistemos.storage import SQLiteStore

pytestmark = pytest.mark.race

CYCLES = 30
CTX = Principal(tenant="acme", agent="a", namespace="hr")


def _engine(tmp_path, tag: str) -> Engine:
    return Engine(SQLiteStore(tmp_path / f"{tag}.db"))


def _run(fns: list) -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        for f in as_completed([pool.submit(fn) for fn in fns]):
            f.result()


def _invariants(eng: Engine) -> None:
    assert eng.verify_integrity() == eng.store.event_count()
    assert eng.verify_index_consistency() is True


@pytest.mark.parametrize("cycle", range(CYCLES))
def test_write_and_search(tmp_path, cycle: int) -> None:
    eng = _engine(tmp_path, f"ws{cycle}")
    fns = []
    for i in range(12):
        fns.append(lambda i=i: eng.assert_fact(CTX, subject=f"e{i}", predicate="p",
                                               object=f"token{i} shared"))
    for _ in range(6):
        fns.append(lambda: eng.search(CTX, text="shared", limit=20))
    _run(fns)
    _invariants(eng)
    assert len(eng.search(CTX, text="shared", limit=50)) == 12  # all writes searchable
    eng.close()


@pytest.mark.parametrize("cycle", range(CYCLES))
def test_supersede_retract_with_search(tmp_path, cycle: int) -> None:
    eng = _engine(tmp_path, f"sr{cycle}")
    seeds = [eng.assert_fact(CTX, subject="Alice", predicate="p", object=f"v{i} word")
             for i in range(6)]
    fns = [lambda s=s: eng.supersede(CTX, s.id, new={"object": "changed word"}) for s in seeds[:3]]
    fns += [lambda s=s: eng.retract(CTX, s.id) for s in seeds[3:]]
    fns += [lambda: eng.search(CTX, text="word", limit=30) for _ in range(6)]
    _run(fns)
    _invariants(eng)
    eng.close()


@pytest.mark.parametrize("cycle", range(CYCLES))
def test_rebuild_with_concurrent_writes(tmp_path, cycle: int) -> None:
    eng = _engine(tmp_path, f"rb{cycle}")
    for i in range(8):
        eng.assert_fact(CTX, subject=f"e{i}", predicate="p", object=f"seed{i} alpha")
    fns = [lambda i=i: eng.assert_fact(CTX, subject=f"n{i}", predicate="p", object=f"new{i} alpha")
           for i in range(8)]
    fns.append(lambda: eng.rebuild_index())
    fns += [lambda: eng.search(CTX, text="alpha", limit=40) for _ in range(4)]
    _run(fns)
    _invariants(eng)
    assert len(eng.search(CTX, text="alpha", limit=50)) == 16
    eng.close()


@pytest.mark.parametrize("cycle", range(CYCLES))
def test_backup_during_writes_and_search(tmp_path, cycle: int) -> None:
    eng = _engine(tmp_path, f"bk{cycle}")
    fns = [lambda i=i: eng.assert_fact(CTX, subject=f"e{i}", predicate="p", object=f"t{i} beta")
           for i in range(10)]
    fns.append(lambda: eng.store.backup(tmp_path / f"bak{cycle}.db"))
    fns += [lambda: eng.search(CTX, text="beta", limit=30) for _ in range(4)]
    _run(fns)
    _invariants(eng)
    eng.close()


@pytest.mark.parametrize("cycle", range(CYCLES))
def test_two_tenants_parallel_no_leak(tmp_path, cycle: int) -> None:
    eng = _engine(tmp_path, f"tt{cycle}")
    ta = Principal(tenant="ta", agent="x", namespace="n")
    tb = Principal(tenant="tb", agent="y", namespace="n")
    fns = [lambda i=i: eng.assert_fact(ta, subject="Alice", predicate="p",
                                       object=f"v{i} sharedterm") for i in range(8)]
    fns += [lambda i=i: eng.assert_fact(tb, subject="Alice", predicate="p",
                                        object=f"v{i} sharedterm") for i in range(8)]
    fns += [lambda: eng.search(ta, text="sharedterm", limit=30) for _ in range(4)]
    _run(fns)
    _invariants(eng)
    # each tenant sees only its own 8 (no cross-tenant leak through the shared index)
    assert len(eng.search(ta, text="sharedterm", limit=50)) == 8
    assert len(eng.search(tb, text="sharedterm", limit=50)) == 8
    eng.close()
