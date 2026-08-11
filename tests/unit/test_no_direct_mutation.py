"""NO_DIRECT_MUTATION_PATH gate (checkpoint A).

Every mutation must go through the ledger. Two properties prove it:

1. every public mutation appends exactly the ledger events it claims to;
2. the queryable projection is a *pure function of the ledger* — clearing it and
   replaying the ledger reproduces byte-identical state. If any method wrote state
   outside the ledger, the rebuild would diverge.
"""

from __future__ import annotations

from epistemos import Engine, Principal
from epistemos.storage import MemoryStore


def _snapshot(engine: Engine, ctx: Principal) -> dict:
    return {
        o["id"]: o
        for o in engine.store.objects(ctx.tenant, ctx.namespace)
    }


def test_every_mutation_appends_to_ledger(engine: Engine, ctx: Principal) -> None:
    before = engine.store.event_count()
    src = engine.add_source(ctx, uri="mem://x")
    assert engine.store.event_count() == before + 1
    f = engine.assert_fact(ctx, subject="A", predicate="p", object="B", source=src.id)
    assert engine.store.event_count() == before + 2
    engine.confirm(ctx, f.id, source=src.id)
    assert engine.store.event_count() == before + 3
    engine.supersede(ctx, f.id, new={"object": "C"})  # supersede = 2 events (close + assert)
    assert engine.store.event_count() == before + 5
    engine.retract(ctx, engine.facts_for(ctx, subject="A", believed_only=True)[0].id)
    assert engine.store.event_count() == before + 6


def test_projection_is_pure_function_of_ledger(engine: Engine, ctx: Principal) -> None:
    src = engine.add_source(ctx, uri="mem://x", trust=0.7)
    e1 = engine.add_entity(ctx, name="Alice")
    e2 = engine.add_entity(ctx, name="Acme")
    engine.add_relation(ctx, source_entity=e1.id, target_entity=e2.id, rel_type="works_at")
    f = engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme", source=src.id)
    engine.record_decision(ctx, statement="hire", evidence=[f.id])
    engine.contradict(
        ctx, f.id,
        by=engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Beta").id,
    )

    before = _snapshot(engine, ctx)
    replayed = engine.rebuild_projection()
    after = _snapshot(engine, ctx)

    assert replayed == engine.store.event_count()
    assert before == after  # identical -> no state lived outside the ledger


def test_rebuild_from_ledger_into_fresh_store(engine: Engine, ctx: Principal) -> None:
    src = engine.add_source(ctx, uri="mem://x")
    engine.assert_fact(ctx, subject="A", predicate="p", object="B", source=src.id)
    dump = engine.export()

    fresh = Engine(MemoryStore())
    fresh.import_events(dump)
    assert fresh.current(ctx, subject="A", predicate="p") == "B"
