"""PROVENANCE_MULTI_HOP gate (checkpoint F).

Chain: SOURCE -> OBSERVATION -> FACT A -> FACT B -> DECISION.
explain(fact) answers WHERE/WHO/WHEN/HASH/DERIVED_FROM/CONFIDENCE/TENANT/AGENT.
explain(decision) answers WHICH FACTS / WHICH ACTIVITIES.
"""

from __future__ import annotations

from epistemos import Engine, Principal


def test_multi_hop_provenance(engine: Engine, ctx: Principal) -> None:
    src = engine.add_source(ctx, uri="mem://doc-7", source_kind="document", trust=0.8)
    obs = engine.observe(ctx, text="Alice joined Acme", source=src.id)
    fa = engine.assert_fact(ctx, subject="Alice", predicate="joined", object="Acme",
                            source=src.id, derived_from=[obs.id])
    fb = engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme",
                            source=src.id, derived_from=[fa.id])
    dec = engine.record_decision(ctx, statement="assign Alice to Acme account",
                                 evidence=[fb.id], outcome="assigned")

    exp = engine.explain(ctx, fb.id)
    # WHERE did it come from
    assert exp["source"]["id"] == src.id
    assert exp["source"]["trust"] == 0.8
    # WHO / WHEN (ledger activities)
    assert exp["activities"], "no provenance activities recorded"
    assert exp["activities"][0]["actor"] == "claude"
    assert exp["owner"] == "claude"
    # CONFIDENCE / TENANT
    assert exp["confidence"] == 1.0
    # DERIVED_FROM multi-hop: fb -> fa -> obs -> source
    assert exp["derived_from"][0]["id"] == fa.id
    assert exp["derived_from"][0]["derived_from"][0]["id"] == obs.id

    # observation carries an input hash (source_hash)
    obs_obj = engine.get(ctx, obs.id)
    assert obs_obj.source_hash is not None

    dexp = engine.explain(ctx, dec.id)
    assert dexp["evidence"][0]["id"] == fb.id
    assert dexp["activities"], "decision has no provenance activity"


def test_confidence_is_not_truth(engine: Engine, ctx: Principal) -> None:
    # A low-trust source can still assert a high-confidence claim: the two dimensions
    # are independent and both are recorded.
    weak = engine.add_source(ctx, uri="mem://rumor", trust=0.05)
    f = engine.assert_fact(ctx, subject="X", predicate="p", object="Y",
                           source=weak.id, confidence=0.99)
    exp = engine.explain(ctx, f.id)
    assert exp["confidence"] == 0.99
    assert exp["source"]["trust"] == 0.05  # trust != confidence
