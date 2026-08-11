"""EXPLAINABLE_RETRIEVAL gate (checkpoint J).

Every result exposes score, score_components, retrieval_method, source, temporal_state and
why_returned. Source trust and fact confidence are separate dimensions.
"""

from __future__ import annotations

from epistemos import Engine, Principal


def test_result_is_explainable(engine: Engine, ctx: Principal) -> None:
    src = engine.add_source(ctx, uri="mem://s", trust=0.9)
    engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme", source=src.id)
    res = engine.search(ctx, text="Alice works Acme", limit=5)
    assert res
    top = res[0]
    for key in ("id", "kind", "score", "score_components", "retrieval_method",
                "source", "temporal_state", "why_returned"):
        assert key in top, key
    assert isinstance(top["why_returned"], str) and top["why_returned"]


def test_exact_component_present_on_structural_match(engine: Engine, ctx: Principal) -> None:
    engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme")
    res = engine.search(ctx, subject="Alice", predicate="works_at", limit=5)
    assert res and "exact" in res[0]["score_components"]


def test_authority_is_separate_from_confidence(engine: Engine, ctx: Principal) -> None:
    low = engine.add_source(ctx, uri="mem://rumor", trust=0.05)
    engine.assert_fact(ctx, subject="Z", predicate="p", object="Q",
                       source=low.id, confidence=0.99)
    res = engine.search(ctx, text="Z p Q", limit=5)
    comp = res[0]["score_components"]
    # authority reflects source trust (low), independent of the high fact confidence
    assert comp.get("authority", 0.0) <= 0.1


def test_temporal_component_marks_historical(engine: Engine, ctx: Principal) -> None:
    f = engine.assert_fact(ctx, subject="A", predicate="p", object="X", valid_from="2026-01-01")
    engine.end_fact(ctx, f.id, valid_to="2026-02-01")  # ended in the past
    res = engine.search(ctx, subject="A", predicate="p", limit=10)
    # the ended (historical) fact scores temporal=0 and says so
    hist = [
        r for r in res
        if r["temporal_state"] and r["temporal_state"]["valid_to"] == "2026-02-01"
    ]
    assert hist
    assert hist[0]["score_components"].get("temporal", 0.0) == 0.0
    assert "NOT currently" in hist[0]["why_returned"]


def test_no_model_component_present(engine: Engine, ctx: Principal) -> None:
    # Default path uses no model: there is no opaque 'vector' score component.
    engine.assert_fact(ctx, subject="A", predicate="p", object="B")
    res = engine.search(ctx, text="A p B")
    assert "vector" not in res[0]["score_components"]
