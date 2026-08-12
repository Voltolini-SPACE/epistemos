"""The P0 leak invariants for the claim graph (EPISTEMOS-05 §14-§17):

    CLAIM_SPACE_LEAK    = 0   a claim outside your spaces is invisible
    EVIDENCE_SPACE_LEAK = 0   evidence outside your spaces is invisible
    REVIEW_SPACE_LEAK   = 0   a review outside your spaces is invisible
    PRIVATE_TO_PUBLIC_LEAK = 0  private evidence never leaks through a public claim (§15)

Every assertion here is a boundary the firewall must hold BEFORE scoring/ranking/traversal.
"""
from __future__ import annotations

import pytest

from epistemos.errors import AuthorizationError, NotFoundError


# ---- CLAIM_SPACE_LEAK = 0 ----------------------------------------------------
def test_private_claim_is_invisible_to_another_agent(cengine, alice, bob) -> None:
    c = cengine.create_claim(alice, subject="salary", predicate="is", object="high")
    assert cengine.get(bob, c.id) is None                 # no read
    with pytest.raises(NotFoundError):
        cengine.belief(bob, c.id)                          # no belief oracle
    with pytest.raises(NotFoundError):
        cengine.explain_claim(bob, c.id)                   # no explain oracle


def test_claim_search_never_returns_a_claim_outside_the_callers_spaces(cengine, alice, bob) -> None:
    c = cengine.create_claim(alice, subject="zebra", predicate="eats", object="grass")
    # alice finds her own claim; bob (no shared space) gets nothing — firewall runs before scoring
    assert any(h["id"] == c.id for h in cengine.search(alice, text="zebra"))
    assert all(h["id"] != c.id for h in cengine.search(bob, text="zebra"))


# ---- EVIDENCE_SPACE_LEAK = 0 -------------------------------------------------
def test_private_evidence_is_invisible_to_another_agent(cengine, alice, bob) -> None:
    ev = cengine.create_evidence(alice, title="dossier", uri="https://x/secret")
    assert cengine.get(bob, ev.id) is None


# ---- REVIEW_SPACE_LEAK = 0 ---------------------------------------------------
def test_review_is_invisible_outside_the_claims_space(cengine, alice, bob, carol) -> None:
    # alice + bob share a team; carol is NOT a member
    sp = cengine.create_space(alice, name="team", visibility="TEAM")
    cengine.grant_capability(alice, space_id=sp.id, agent=bob.agent)
    c = cengine.create_claim(alice, subject="x", predicate="=", object="1", space=sp.id)
    cengine.review_claim(bob, c.id, verdict="dispute", rationale="leak me if you can")
    # carol cannot see the claim, and therefore cannot see its reviews
    assert cengine.get(carol, c.id) is None
    with pytest.raises(NotFoundError):
        cengine.explain_claim(carol, c.id)


def test_belief_is_computed_only_over_readable_reviews(cengine, alice, bob, carol) -> None:
    # A claim is COMMUNITY-visible (everyone in tenant reads it), but a dispute lives in a review
    # placed in the claim's space; a reader who can see the claim sees the review because a review
    # inherits the claim's audience. This checks the *converse*: a reader who cannot see the claim
    # gets no belief at all (covered above), and belief over the SAME claim is identical for two
    # members — i.e. no reviewer is silently dropped.
    sp = cengine.create_space(alice, name="team", visibility="TEAM")
    for m in (bob, carol):
        cengine.grant_capability(alice, space_id=sp.id, agent=m.agent)
    c = cengine.create_claim(alice, subject="x", predicate="=", object="1", space=sp.id)
    cengine.review_claim(bob, c.id, verdict="confirm")
    cengine.review_claim(carol, c.id, verdict="dispute")
    assert cengine.belief(bob, c.id)["state"] == cengine.belief(carol, c.id)["state"] == "disputed"


# ---- PRIVATE_TO_PUBLIC_LEAK = 0 (visibility composition, §15) ----------------
def test_public_claim_does_not_expose_private_evidence(cengine, alice, bob, curator) -> None:
    # alice makes a claim visible org-wide, attaches PRIVATE evidence (her own, no space).
    org = cengine.create_space(curator, name="org", visibility="ORGANIZATION")
    c = cengine.create_claim(curator, subject="merger", predicate="approved", object="yes",
                             space=org.id)
    secret = cengine.create_evidence(alice, title="board memo", uri="https://x/board")  # PRIVATE
    # alice can attach because she reads both (the org claim + her own evidence)
    cengine.attach_evidence(alice, evidence_id=secret.id, to_claim=c.id, relation="supports")

    # bob reads the public claim but must NOT see the private evidence behind it
    assert cengine.get(bob, c.id) is not None
    assert cengine.claim_evidence(bob, c.id) == []             # filtered by evidence readability
    ex = cengine.explain_claim(bob, c.id)
    assert ex["evidence"] == []
    # the owner of the evidence still sees it
    assert len(cengine.claim_evidence(alice, c.id)) == 1


def test_attach_requires_read_of_both_sides(cengine, alice, bob) -> None:
    # bob cannot attach alice's private evidence he can't read to a claim
    c = cengine.create_claim(bob, subject="x", predicate="=", object="1")
    secret = cengine.create_evidence(alice, title="hidden", uri="https://x/h")
    with pytest.raises(NotFoundError):
        cengine.attach_evidence(bob, evidence_id=secret.id, to_claim=c.id, relation="supports")


# ---- cross-tenant is absolute -----------------------------------------------
def test_claims_never_cross_a_tenant_boundary(cengine, alice) -> None:
    from tests.claims.conftest import principal
    other = principal("mallory", tenant="evilcorp")
    c = cengine.create_claim(alice, subject="x", predicate="=", object="1")
    assert cengine.get(other, c.id) is None
    with pytest.raises(NotFoundError):
        cengine.explain_claim(other, c.id)


# ---- promotion to ORG+ is gated ---------------------------------------------
def test_placing_a_claim_into_org_space_requires_the_promote_gate(cengine, alice, bob) -> None:
    org = cengine.create_space(bob, name="org", visibility="ORGANIZATION")
    # alice lacks knowledge.promote; she cannot mint a claim straight into an ORG space
    with pytest.raises(AuthorizationError):
        cengine.create_claim(alice, subject="x", predicate="=", object="1", space=org.id)
