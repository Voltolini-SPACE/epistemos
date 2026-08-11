"""ENTITY_MERGE_LINEAGE gate (checkpoint E).

Identity is deterministic and never auto-resolved by string similarity: "OpenAI",
"Open AI" and "OPENAI" are three distinct entities until an explicit, traceable merge.
"""

from __future__ import annotations

from epistemos import Engine, Principal


def test_similar_names_are_distinct_by_default(engine: Engine, ctx: Principal) -> None:
    a = engine.add_entity(ctx, name="OpenAI")
    b = engine.add_entity(ctx, name="Open AI")
    c = engine.add_entity(ctx, name="OPENAI")
    assert len({a.id, b.id, c.id}) == 3
    # nothing was auto-merged
    for e in (a, b, c):
        got = engine.get(ctx, e.id)
        assert "merged_into" not in got.metadata


def test_explicit_merge_is_traceable_and_nondestructive(engine: Engine, ctx: Principal) -> None:
    canon = engine.add_entity(ctx, name="OpenAI")
    dup = engine.add_entity(ctx, name="Open AI")
    engine.merge_entities(ctx, canonical=canon.id, duplicates=[dup.id])

    canon2 = engine.get(ctx, canon.id)
    dup2 = engine.get(ctx, dup.id)
    assert "Open AI" in canon2.aliases  # canonical absorbed the alias
    assert dup.id in canon2.metadata["merged_from"]
    assert dup2 is not None  # duplicate NOT deleted
    assert dup2.metadata["merged_into"] == canon.id  # lineage preserved


def test_split_reverses_with_lineage(engine: Engine, ctx: Principal) -> None:
    origin = engine.add_entity(ctx, name="Ambiguous Corp")
    parts = engine.split_entity(ctx, origin.id, into=[{"name": "Corp US"}, {"name": "Corp EU"}])
    assert len(parts) == 2
    origin2 = engine.get(ctx, origin.id)
    assert origin2.metadata["split_into"] == [p.id for p in parts]
    for p in parts:
        assert engine.get(ctx, p.id).metadata["split_from"] == origin.id


def test_merge_is_a_ledger_event(engine: Engine, ctx: Principal) -> None:
    canon = engine.add_entity(ctx, name="A")
    dup = engine.add_entity(ctx, name="B")
    before = engine.store.event_count()
    engine.merge_entities(ctx, canonical=canon.id, duplicates=[dup.id])
    assert engine.store.event_count() == before + 1
    assert engine.verify_integrity() == engine.store.event_count()
