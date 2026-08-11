"""STORE_CONFORMANCE gate (checkpoint M).

One battery, no store-specific branching (the `engine` fixture is parametrized over both
MemoryStore and SQLiteStore). Exercises facts/events/timeline/provenance/decisions/
contradictions/supersession/retraction/transactions/integrity/export in a single flow.
"""

from __future__ import annotations

from epistemos import Engine, Principal
from epistemos.storage import MemoryStore, SQLiteStore


def test_full_capability_flow(engine: Engine, ctx: Principal) -> None:
    src = engine.add_source(ctx, uri="mem://s", trust=0.7)
    obs = engine.observe(ctx, text="note", source=src.id)
    f1 = engine.assert_fact(ctx, subject="A", predicate="p", object="X",
                            source=src.id, derived_from=[obs.id])
    engine.confirm(ctx, f1.id, source=src.id)
    f2 = engine.supersede(ctx, f1.id, new={"object": "Y"})
    f3 = engine.assert_fact(ctx, subject="A", predicate="p", object="Z")
    engine.contradict(ctx, f2.id, by=f3.id)
    engine.retract(ctx, f3.id)
    dec = engine.record_decision(ctx, statement="d", evidence=[f2.id])

    # facts / timeline
    assert engine.current(ctx, subject="A", predicate="p") == "Y"
    tl = engine.timeline(ctx, subject="A", predicate="p")
    assert len(tl) == 3  # f1(superseded), f2(believed), f3(retracted)

    # provenance / decisions
    assert engine.explain(ctx, dec.id)["evidence"][0]["id"] == f2.id
    assert engine.explain(ctx, f1.id)["derived_from"][0]["id"] == obs.id

    # integrity / export
    n = engine.verify_integrity()
    assert n == engine.store.event_count()
    assert engine.export()["event_count"] == n


def test_both_stores_agree_on_logical_state(tmp_path) -> None:
    ctx = Principal(tenant="t", agent="a", namespace="n")

    def run(engine: Engine) -> tuple:
        s = engine.add_source(ctx, uri="mem://s", trust=0.6)
        f = engine.assert_fact(ctx, subject="A", predicate="p", object="X", source=s.id)
        engine.supersede(ctx, f.id, new={"object": "Y"})
        return (
            engine.current(ctx, subject="A", predicate="p"),
            len(engine.timeline(ctx, subject="A")),
            engine.store.event_count(),
        )

    mem = run(Engine(MemoryStore()))
    sql = run(Engine(SQLiteStore(tmp_path / "c.db")))
    assert mem == sql
