"""QUALITY_CORPUS gate (checkpoint AA).

An adversarial corpus with deterministic expected semantics (no LLM). Each category the
mission lists — current / historical / retroactive correction / contradictory source /
alias ambiguity / duplicate entity / low-trust source / stale / superseded / multi-hop
provenance / decision precedent — has an explicit expected answer the engine must produce.
"""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal


@pytest.fixture
def corpus(engine: Engine, ctx: Principal) -> dict:
    hr = engine.add_source(ctx, uri="mem://hr-system", source_kind="api", trust=0.9)
    rumor = engine.add_source(ctx, uri="mem://watercooler", source_kind="note", trust=0.05)

    # historical + current employment, modelled bitemporally
    f_alpha = engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Alpha",
                                 valid_from="2026-01-01", valid_to="2026-02-01", source=hr.id)
    f_beta = engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Beta",
                                valid_from="2026-02-01", source=hr.id)

    # a wrong fact that gets retroactively corrected
    f_title = engine.assert_fact(ctx, subject="Bob", predicate="title", object="Manager",
                                 valid_from="2026-01-01", source=hr.id)
    t_before = f_title.tx_from
    engine.supersede(ctx, f_title.id,
                     new={"object": "Director", "valid_from": "2026-01-01"},
                     reason="HR correction")

    # a low-trust contradictory rumor about Alice
    f_rumor = engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Gamma",
                                 source=rumor.id)
    engine.contradict(ctx, f_rumor.id, by=f_beta.id, note="rumor vs HR record")

    # alias ambiguity + duplicate entity resolution
    e_openai = engine.add_entity(ctx, name="OpenAI")
    e_open_ai = engine.add_entity(ctx, name="Open AI")
    engine.merge_entities(ctx, canonical=e_openai.id, duplicates=[e_open_ai.id])

    # multi-hop provenance -> decision
    obs = engine.observe(ctx, text="Alice leads the Beta project", source=hr.id)
    f_lead = engine.assert_fact(ctx, subject="Alice", predicate="leads", object="Beta-project",
                                source=hr.id, derived_from=[obs.id])
    decision = engine.record_decision(ctx, statement="Assign Alice as Beta project owner",
                                      evidence=[f_beta.id, f_lead.id], outcome="assigned")

    return dict(hr=hr, rumor=rumor, f_alpha=f_alpha, f_beta=f_beta, f_title=f_title,
                t_before=t_before, f_rumor=f_rumor, e_openai=e_openai, e_open_ai=e_open_ai,
                obs=obs, f_lead=f_lead, decision=decision)


def test_current_and_historical(engine: Engine, ctx: Principal, corpus: dict) -> None:
    # current (clock is 2026-06): Beta
    assert engine.current(ctx, subject="Alice", predicate="works_at") == "Beta"
    # historical: on Jan-15 Alice was at Alpha
    assert engine.as_of(ctx, "2026-01-15", subject="Alice", predicate="works_at") == "Alpha"


def test_retroactive_correction(engine: Engine, ctx: Principal, corpus: dict) -> None:
    # what we believed at T_before: Manager; what we believe now about Jan: Director
    assert engine.as_of(ctx, "2026-01-15", subject="Bob", predicate="title",
                        at_tx=corpus["t_before"]) == "Manager"
    assert engine.as_of(ctx, "2026-01-15", subject="Bob", predicate="title") == "Director"


def test_superseded_fact_is_kept_not_deleted(engine: Engine, ctx: Principal, corpus: dict) -> None:
    old = engine.get(ctx, corpus["f_title"].id)
    assert old is not None and old.status == "superseded"


def test_low_trust_source_scores_low_authority(
    engine: Engine, ctx: Principal, corpus: dict
) -> None:
    results = engine.search(ctx, subject="Alice", predicate="works_at", object="Gamma", limit=5)
    rumor_hit = next(r for r in results if r["id"] == corpus["f_rumor"].id)
    assert rumor_hit["score_components"].get("authority", 0.0) <= 0.1


def test_contradiction_recorded_both_ways(engine: Engine, ctx: Principal, corpus: dict) -> None:
    rumor = engine.get(ctx, corpus["f_rumor"].id)
    beta = engine.get(ctx, corpus["f_beta"].id)
    assert corpus["f_beta"].id in rumor.contradicts
    assert corpus["f_rumor"].id in beta.contradicts


def test_alias_ambiguity_not_auto_resolved(engine: Engine, ctx: Principal, corpus: dict) -> None:
    # distinct ids; explicit merge left lineage, did not delete the duplicate
    assert corpus["e_openai"].id != corpus["e_open_ai"].id
    dup = engine.get(ctx, corpus["e_open_ai"].id)
    assert dup.metadata["merged_into"] == corpus["e_openai"].id
    canon = engine.get(ctx, corpus["e_openai"].id)
    assert "Open AI" in canon.aliases


def test_multi_hop_provenance_and_decision_precedent(
    engine: Engine, ctx: Principal, corpus: dict
) -> None:
    exp = engine.explain(ctx, corpus["f_lead"].id)
    assert exp["derived_from"][0]["id"] == corpus["obs"].id  # fact <- observation
    dexp = engine.explain(ctx, corpus["decision"].id)
    ev_ids = {e["id"] for e in dexp["evidence"]}
    assert corpus["f_beta"].id in ev_ids and corpus["f_lead"].id in ev_ids


def test_why_do_we_believe_it(engine: Engine, ctx: Principal, corpus: dict) -> None:
    # the corpus's headline question: where does Alice work NOW, and why?
    tl = engine.timeline(ctx, subject="Alice", predicate="works_at")
    # Beta (HR, trust 0.9) and Gamma (rumor, trust 0.05) are both believed;
    # authority-aware resolution makes the HR-backed Beta current, not the newer rumor.
    assert engine.current(ctx, subject="Alice", predicate="works_at") == "Beta"
    # the stale Alpha row is present but not believed-as-current (validity ended)
    alpha_rows = [r for r in tl if r["statement"]["object"] == "Alpha"]
    assert alpha_rows and alpha_rows[0]["valid_to"] == "2026-02-01"
