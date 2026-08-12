"""Value model + pure belief derivation (EPISTEMOS-05 §3-§10). No engine, no store."""
from __future__ import annotations

from epistemos.claims import (
    BeliefState,
    Claim,
    ClaimStatus,
    ContributorKind,
    Evidence,
    EvidenceRelation,
    Verdict,
)
from epistemos.claims.belief import derive_belief


def _claim(**over):
    base = dict(
        id="clm_1", kind="claim", tenant="t", namespace="n", owner="ingestor",
        created_at="2026-01-01T00:00:00Z", source=None, confidence=1.0, derived_from=(),
        spaces=(), metadata={}, subject="X", predicate="is", object="Y",
        claimant="alice", contributor_kind=ContributorKind.AGENT.value,
        valid_from=None, valid_to=None, tx_from="2026-01-01T00:00:00Z", tx_to=None,
        status=ClaimStatus.OPEN.value,
    )
    base.update(over)
    return base


# -- identity separation (§3): owner != claimant != source ---------------------
def test_claim_keeps_three_identities_distinct() -> None:
    c = Claim.from_dict(_claim(owner="ingestor", claimant="dr_who", source="src_pubmed"))
    assert c.owner == "ingestor"       # the ingesting agent
    assert c.claimant == "dr_who"      # who asserts it
    assert c.source == "src_pubmed"    # external origin
    assert c.to_dict()["claimant"] == "dr_who"


def test_claim_roundtrips_through_dict() -> None:
    c = Claim.from_dict(_claim())
    assert Claim.from_dict(c.to_dict()).to_dict() == c.to_dict()


def test_evidence_is_a_reference_not_a_copy() -> None:
    e = Evidence.from_dict({
        "id": "evd_1", "kind": "evidence", "tenant": "t", "namespace": "n", "owner": "o",
        "created_at": "2026-01-01T00:00:00Z", "spaces": (), "metadata": {},
        "evidence_kind": "document", "title": "filing", "uri": "https://x/doc",
        "content_hash": "deadbeef", "origin": "SEC", "captured_at": None,
    })
    assert e.uri == "https://x/doc" and e.content_hash == "deadbeef"  # ref, not the bytes


def test_enums_are_closed_vocabularies() -> None:
    assert {v.value for v in Verdict} == {
        "confirm", "dispute", "reject", "request_evidence", "abstain"}
    assert {r.value for r in EvidenceRelation} == {
        "supports", "contradicts", "weakens", "derived_from"}


# -- belief is DERIVED and explainable (§10) -----------------------------------
def test_no_reviews_is_proposed_not_believed() -> None:
    b = derive_belief(_claim(), [])
    assert b["state"] == str(BeliefState.PROPOSED)
    assert b["why"]


def test_a_single_confirm_supports_but_does_not_accept() -> None:
    b = derive_belief(_claim(), [{"verdict": "confirm", "owner": "bob"}])
    assert b["state"] == str(BeliefState.SUPPORTED)  # supported != accepted (§ contribution!=truth)


def test_dispute_makes_it_disputed_even_against_many_confirms() -> None:
    reviews = [{"verdict": "confirm", "owner": f"a{i}"} for i in range(5)]
    reviews.append({"verdict": "dispute", "owner": "skeptic"})
    b = derive_belief(_claim(), reviews)
    assert b["state"] == str(BeliefState.DISPUTED)  # majority is NOT truth (§9)


def test_governed_acceptance_dominates_but_records_coexisting_dispute() -> None:
    reviews = [{"verdict": "confirm", "owner": "a"}, {"verdict": "dispute", "owner": "b"}]
    b = derive_belief(_claim(), reviews, accepted={"actor": "curator", "at": "t"})
    assert b["state"] == str(BeliefState.ACCEPTED)
    assert "dispute" in b["why"].lower()  # acceptance does not erase the dispute


def test_retracted_claim_short_circuits_to_retracted() -> None:
    b = derive_belief(_claim(status=ClaimStatus.RETRACTED.value),
                      [{"verdict": "confirm", "owner": "a"}])
    assert b["state"] == str(BeliefState.RETRACTED)


def test_rejection_beats_acceptance_material_if_both_present() -> None:
    # a claim can't be both, but the derivation must order deterministically: rejected wins
    b = derive_belief(_claim(), [], accepted={"actor": "x"}, rejected={"actor": "y"})
    assert b["state"] == str(BeliefState.REJECTED)
