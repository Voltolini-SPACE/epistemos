"""End-to-end claim pipeline over the real Engine: assert → evidence → review → govern → explain,
plus ledger-rebuild equivalence and bitemporal lifecycle (EPISTEMOS-05 §3-§18)."""
from __future__ import annotations

import pytest

from epistemos import Engine, Principal
from epistemos.errors import ConflictError, NotFoundError, ValidationError


def _shared_team(eng: Engine, owner: Principal, *members: Principal) -> str:
    sp = eng.create_space(owner, name="team", visibility="TEAM")
    for m in members:
        eng.grant_capability(owner, space_id=sp.id, agent=m.agent)
    return sp.id


def test_full_pipeline_produces_explainable_belief(cengine, alice, bob, curator) -> None:
    sp = _shared_team(cengine, alice, bob, curator)
    c = cengine.create_claim(alice, subject="Orion", predicate="launched", object="2026",
                             space=sp)
    ev = cengine.create_evidence(alice, evidence_kind="document", title="press release",
                                 uri="https://x/pr", content_hash="h1", space=sp)
    cengine.attach_evidence(alice, evidence_id=ev.id, to_claim=c.id, relation="supports")
    cengine.review_claim(bob, c.id, verdict="confirm", rationale="saw the launch")

    b = cengine.belief(bob, c.id)
    assert b["state"] == "supported"           # supported, not yet accepted
    ex = cengine.explain_claim(bob, c.id)
    assert ex["claimant"] == "alice" and ex["ingested_by"] == "alice"
    assert len(ex["evidence"]) == 1 and ex["evidence"][0]["relation"] == "supports"
    assert len(ex["reviews"]) == 1

    cengine.accept_claim(curator, c.id, reason="verified against filing")
    assert cengine.belief(curator, c.id)["state"] == "accepted"


def test_contribution_is_not_truth_a_bare_claim_is_only_proposed(cengine, alice) -> None:
    c = cengine.create_claim(alice, subject="A", predicate="beats", object="B")
    assert cengine.belief(alice, c.id)["state"] == "proposed"  # existence != belief


def test_retract_is_append_only_and_first_close_wins(cengine, alice) -> None:
    c = cengine.create_claim(alice, subject="A", predicate="is", object="B")
    cengine.retract_claim(alice, c.id, reason="mistake")
    assert cengine.belief(alice, c.id)["state"] == "retracted"
    with pytest.raises(ConflictError):
        cengine.retract_claim(alice, c.id)  # cannot double-close


def test_evidence_can_contradict_a_claim(cengine, alice, bob, curator) -> None:
    sp = _shared_team(cengine, alice, bob)
    c = cengine.create_claim(alice, subject="Earth", predicate="is", object="flat", space=sp)
    ev = cengine.create_evidence(alice, evidence_kind="dataset", title="geodesy",
                                 uri="https://x/geo", space=sp)
    cengine.attach_evidence(bob, evidence_id=ev.id, to_claim=c.id, relation="contradicts")
    links = cengine.claim_evidence(bob, c.id)
    assert links[0]["relation"] == "contradicts"  # 'attached' != 'supports' (§6)


def test_multiple_reviewers_disagree_and_both_survive(cengine, alice, bob, carol) -> None:
    sp = _shared_team(cengine, alice, bob, carol)
    c = cengine.create_claim(alice, subject="X", predicate="=", object="1", space=sp)
    cengine.review_claim(bob, c.id, verdict="confirm")
    cengine.review_claim(carol, c.id, verdict="dispute", rationale="counterexample")
    b = cengine.belief(alice, c.id)
    assert b["state"] == "disputed"
    verdicts = {r["verdict"] for r in b["reviews"]}
    assert verdicts == {"confirm", "dispute"}  # neither review is out-voted away


def test_reject_keeps_the_claim_on_record(cengine, alice, curator) -> None:
    sp = _shared_team(cengine, alice, curator)
    c = cengine.create_claim(alice, subject="X", predicate="=", object="2", space=sp)
    cengine.reject_claim(curator, c.id, reason="unsupported")
    assert cengine.belief(curator, c.id)["state"] == "rejected"
    assert cengine.get(curator, c.id) is not None  # never deleted


def test_wrong_object_kind_is_rejected(cengine, alice) -> None:
    # a Fact is not a Claim: the owner (who *can* read it) hits the type check, not the firewall
    f = cengine.assert_fact(alice, subject="s", predicate="p", object="o")
    with pytest.raises(ValidationError):
        cengine.review_claim(alice, f.id, verdict="confirm")


def test_govern_across_the_space_boundary_is_a_nonexistence_not_a_typeerror(
    cengine, alice, curator
) -> None:
    # curator cannot even see alice's PRIVATE claim: refusal must be NotFoundError (no oracle §17)
    c = cengine.create_claim(alice, subject="secret", predicate="is", object="x")
    with pytest.raises(NotFoundError):
        cengine.accept_claim(curator, c.id)


def test_rebuild_projection_equals_replay_with_claims(cengine, alice, bob, curator) -> None:
    sp = _shared_team(cengine, alice, bob, curator)
    c = cengine.create_claim(alice, subject="Q", predicate="is", object="42", space=sp)
    ev = cengine.create_evidence(alice, title="e", uri="https://x/e", space=sp)
    cengine.attach_evidence(alice, evidence_id=ev.id, to_claim=c.id, relation="supports")
    cengine.review_claim(bob, c.id, verdict="confirm")
    cengine.accept_claim(curator, c.id)

    before = cengine.explain_claim(curator, c.id)
    cengine.rebuild_projection()
    after = cengine.explain_claim(curator, c.id)
    assert before == after  # the claim graph is a pure projection of the ledger


def test_claim_is_bitemporal(cengine, alice) -> None:
    c = cengine.create_claim(alice, subject="s", predicate="p", object="o",
                             valid_from="2020-01-01T00:00:00Z")
    ex = cengine.explain_claim(alice, c.id)
    assert ex["temporal"]["valid_from"] == "2020-01-01T00:00:00Z"
    assert ex["temporal"]["tx_from"] and ex["temporal"]["status"] == "open"


def test_self_review_is_disclosed_not_hidden(cengine, alice) -> None:
    c = cengine.create_claim(alice, subject="s", predicate="p", object="o")
    cengine.review_claim(alice, c.id, verdict="confirm", rationale="i'm sure")  # claimant reviews
    ex = cengine.explain_claim(alice, c.id)
    assert ex["reviews"][0]["self_review"] is True  # visible, not silently dropped


def test_claimant_can_differ_from_ingesting_agent(cengine, alice) -> None:
    c = cengine.create_claim(alice, subject="s", predicate="p", object="o",
                             claimant="external_analyst", contributor_kind="human")
    ex = cengine.explain_claim(alice, c.id)
    assert ex["claimant"] == "external_analyst" and ex["ingested_by"] == "alice"
