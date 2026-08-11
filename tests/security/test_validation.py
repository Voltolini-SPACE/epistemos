"""Input-validation attacks (checkpoint U: S10-S14, S41-S50). Fail closed."""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal
from epistemos.errors import ValidationError

pytestmark = pytest.mark.security


def test_s41_malformed_timestamp(engine: Engine, ctx: Principal) -> None:
    with pytest.raises(ValidationError):
        engine.assert_fact(ctx, subject="A", predicate="p", object="B", valid_from="not-a-date")
    with pytest.raises(ValidationError):
        engine.assert_fact(ctx, subject="A", predicate="p", object="B", valid_from="2026-13-99")


def test_s42_nan_inf_confidence(engine: Engine, ctx: Principal) -> None:
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            engine.assert_fact(ctx, subject="A", predicate="p", object="B", confidence=bad)


def test_s43_control_chars_and_nul(engine: Engine, ctx: Principal) -> None:
    with pytest.raises(ValidationError):
        engine.assert_fact(ctx, subject="A\x00B", predicate="p", object="B")
    with pytest.raises(ValidationError):
        engine.assert_fact(ctx, subject="A\x07bell", predicate="p", object="B")


def test_s44_oversized_metadata(engine: Engine, ctx: Principal) -> None:
    huge = {"blob": "x" * (70 * 1024)}
    with pytest.raises(ValidationError):
        engine.assert_fact(ctx, subject="A", predicate="p", object="B", metadata=huge)


def test_s45_deeply_nested_metadata(engine: Engine, ctx: Principal) -> None:
    nested: dict = {}
    cur = nested
    for _ in range(40):
        cur["n"] = {}
        cur = cur["n"]
    with pytest.raises(ValidationError):
        engine.assert_fact(ctx, subject="A", predicate="p", object="B", metadata=nested)


def test_s46_ids_are_engine_generated_and_unique(engine: Engine, ctx: Principal) -> None:
    a = engine.assert_fact(ctx, subject="A", predicate="p", object="B")
    b = engine.assert_fact(ctx, subject="A", predicate="p", object="B")
    assert a.id != b.id  # no external id acceptance -> no duplicate-id injection


def test_s47_hash_contract_deterministic_and_distinct() -> None:
    from epistemos._util import hash_obj

    assert hash_obj({"a": 1, "b": 2}) == hash_obj({"b": 2, "a": 1})  # canonical
    assert hash_obj({"a": 1}) != hash_obj({"a": 2})  # distinct content -> distinct hash


def test_s48_import_takes_data_not_paths() -> None:
    from epistemos.errors import SchemaError
    from epistemos.storage import MemoryStore

    eng = Engine(MemoryStore())
    # a malformed record (missing hashes) is rejected, not silently trusted
    with pytest.raises(SchemaError):
        eng.import_events({"format": "epistemos-events", "schema_version": 1,
                           "events": [{"seq": 1, "op": "x"}]})


def test_s12_oversized_document(engine: Engine, ctx: Principal) -> None:
    big = "x" * (6 * 1024 * 1024)  # > 5 MiB cap
    with pytest.raises(ValidationError):
        engine.ingest_document(ctx, title="t", text=big)


def test_s10_hostile_mime_rejected(engine: Engine, ctx: Principal) -> None:
    with pytest.raises(ValidationError):
        engine.ingest_document(ctx, title="t", text="x", mime="application/x-msdownload")


def test_s50_namespace_unicode_confusable_rejected() -> None:
    # zero-width space and non-ASCII confusables are not valid identifiers
    with pytest.raises(ValidationError):
        Principal(tenant="acme", agent="a", namespace="hr​")
    with pytest.raises(ValidationError):
        Principal(tenant="аcme", agent="a")  # Cyrillic 'а' confusable


def test_s13_graph_traversal_is_bounded(engine: Engine, ctx: Principal) -> None:
    # build a long chain; traversal respects the hop cap (no unbounded expansion)
    prev = engine.add_entity(ctx, name="n0")
    for i in range(1, 30):
        cur = engine.add_entity(ctx, name=f"n{i}")
        engine.add_relation(ctx, source_entity=prev.id, target_entity=cur.id, rel_type="next")
        prev = cur
    start = engine.facts_for  # noqa: F841 - clarity only
    first = engine.search(ctx, text="n0", kinds=("entity",))[0]["id"]
    sub = engine.query_graph(ctx, first, max_hops=2)
    # hop cap keeps the visited set small relative to the 30-node chain
    assert len(sub["nodes"]) <= 5


def test_uri_path_traversal_stored_inert(engine: Engine, ctx: Principal) -> None:
    src = engine.add_source(ctx, uri="../../../../etc/passwd")
    assert engine.get(ctx, src.id).uri == "../../../../etc/passwd"  # data, never opened
