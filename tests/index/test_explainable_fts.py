"""EXPLAINABLE_FTS gate (ETAPA 4). FTS results keep the full explainable contract."""

from __future__ import annotations

from epistemos import Engine, Principal


def test_fts_result_carries_all_explainability(fts: Engine, ctx: Principal) -> None:
    src = fts.add_source(ctx, uri="mem://hr", trust=0.9)
    fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme", source=src.id)
    res = fts.search(ctx, text="Alice Acme", limit=5)
    assert res
    top = res[0]
    # method proves the FTS path was used (not silent fallback)
    assert top["retrieval_method"].startswith("fts5-bm25")
    for key in ("id", "kind", "score", "score_components", "retrieval_method",
                "source", "temporal_state", "why_returned"):
        assert key in top, key
    comp = top["score_components"]
    # at minimum: lexical + temporal + authority contributions, exact when applicable
    assert "lexical" in comp and 0.0 <= comp["lexical"] <= 1.0
    assert "temporal" in comp
    assert "authority" in comp
    assert isinstance(top["why_returned"], str) and "lexical overlap" in top["why_returned"]


def test_authority_and_confidence_stay_separate(fts: Engine, ctx: Principal) -> None:
    low = fts.add_source(ctx, uri="mem://rumor", trust=0.05)
    fts.assert_fact(ctx, subject="Zeta", predicate="p", object="Quux",
                    source=low.id, confidence=0.99)
    res = fts.search(ctx, text="Zeta Quux", limit=5)
    assert res[0]["score_components"].get("authority", 0.0) <= 0.1  # trust, not confidence


def test_exact_component_present_with_text(fts: Engine, ctx: Principal) -> None:
    fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme")
    res = fts.search(ctx, text="Alice", subject="Alice", predicate="works_at", limit=5)
    assert res and "exact" in res[0]["score_components"]
