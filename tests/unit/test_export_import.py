"""EXPORT_IMPORT gate (checkpoint O).

Versioned, human-readable (JSON) export; DB A -> export -> DB B -> import -> logical
equivalence; a 1-byte tamper is detected when integrity is verified.
"""

from __future__ import annotations

import copy

import pytest

from epistemos import Engine, Principal
from epistemos.errors import ConflictError, IntegrityError, SchemaError
from epistemos.storage import MemoryStore


def _populate(engine: Engine, ctx: Principal) -> None:
    s = engine.add_source(ctx, uri="mem://s", trust=0.7)
    e1 = engine.add_entity(ctx, name="Alice")
    e2 = engine.add_entity(ctx, name="Acme")
    engine.add_relation(ctx, source_entity=e1.id, target_entity=e2.id, rel_type="works_at")
    f = engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme", source=s.id)
    engine.supersede(ctx, f.id, new={"object": "Beta"})
    engine.record_decision(ctx, statement="staff", evidence=[
        engine.facts_for(ctx, subject="Alice", believed_only=True)[0].id
    ])


def test_roundtrip_logical_equivalence(engine: Engine, ctx: Principal) -> None:
    _populate(engine, ctx)
    dump = engine.export()
    assert dump["format"] == "epistemos-events"
    assert dump["schema_version"] == 1
    assert dump["events"]

    fresh = Engine(MemoryStore())
    imported = fresh.import_events(dump)
    assert imported == dump["event_count"]
    assert fresh.verify_integrity() == engine.verify_integrity()
    assert fresh.current(ctx, subject="Alice", predicate="works_at") == \
        engine.current(ctx, subject="Alice", predicate="works_at")
    assert fresh.store.counts(ctx.tenant, ctx.namespace) == \
        engine.store.counts(ctx.tenant, ctx.namespace)


def test_one_byte_tamper_detected(engine: Engine, ctx: Principal) -> None:
    _populate(engine, ctx)
    dump = engine.export()
    tampered = copy.deepcopy(dump)
    # flip a single value in a historical payload
    tampered["events"][3]["payload"]["subject"] = "Mallory"
    fresh = Engine(MemoryStore())
    with pytest.raises(IntegrityError):
        fresh.import_events(tampered)


def test_import_into_nonempty_refused(engine: Engine, ctx: Principal) -> None:
    _populate(engine, ctx)
    dump = engine.export()
    other = Engine(MemoryStore())
    other.add_source(ctx, uri="mem://x")
    with pytest.raises(ConflictError):
        other.import_events(dump)


def test_bad_format_and_schema_rejected() -> None:
    fresh = Engine(MemoryStore())
    with pytest.raises(SchemaError):
        fresh.import_events({"format": "not-ours", "events": []})
    with pytest.raises(SchemaError):
        fresh.import_events({"format": "epistemos-events", "schema_version": 99, "events": []})
