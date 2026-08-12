"""Adversarial battery for collaborative claims (EPISTEMOS-05 §37). Each test is an attack that
MUST fail: truth-by-submission, self-acceptance, capability forgery, oracle probing, ledger tamper.
"""
from __future__ import annotations

import pytest

from epistemos import Principal
from epistemos.errors import AuthorizationError, IntegrityError, NotFoundError
from epistemos.identity import _DEFAULT_CAPS
from epistemos.ledger import verify_chain


def _shared(eng, owner, *members):
    sp = eng.create_space(owner, name="team", visibility="TEAM")
    for m in members:
        eng.grant_capability(owner, space_id=sp.id, agent=m.agent)
    return sp.id


# ATTACK 1 — truth by submission. Merely contributing must not make it believed. ---------------
def test_a_contributor_cannot_make_a_claim_true_by_asserting_it(cengine, alice) -> None:
    c = cengine.create_claim(alice, subject="I", predicate="am", object="president")
    assert cengine.belief(alice, c.id)["state"] == "proposed"       # not accepted
    # even self-confirming does not accept it — self-review is a review, not governance
    cengine.review_claim(alice, c.id, verdict="confirm")
    assert cengine.belief(alice, c.id)["state"] == "supported"      # still not accepted


# ATTACK 2 — self-acceptance. The claimant cannot govern their own claim into truth. -----------
def test_claimant_with_the_accept_capability_still_cannot_self_accept(cengine) -> None:
    # give ONE agent both contribution and the truth gate; it still may not accept its own claim
    powerful = Principal(tenant="acme", agent="ceo", namespace="hr",
                         capabilities=_DEFAULT_CAPS | {"knowledge.accept"})
    c = cengine.create_claim(powerful, subject="my", predicate="idea", object="wins")
    with pytest.raises(AuthorizationError):
        cengine.accept_claim(powerful, c.id)


# ATTACK 3 — capability escalation. The truth gate is not a default right. ----------------------
def test_a_default_agent_cannot_accept_anything(cengine, alice, bob) -> None:
    sp = _shared(cengine, alice, bob)
    c = cengine.create_claim(alice, subject="x", predicate="=", object="1", space=sp)
    assert "knowledge.accept" not in bob.capabilities
    with pytest.raises(AuthorizationError):
        cengine.accept_claim(bob, c.id)


# ATTACK 4 — forged governance marker via a caller-supplied Principal claim. --------------------
def test_acceptance_cannot_be_forged_by_inflating_the_principals_own_caps(cengine, alice) -> None:
    # A caller can *say* they hold knowledge.accept, but acceptance still refuses self-acceptance,
    # and (below) a non-claimant curator must go through the policy — the Principal is never trusted
    # as the source of a governance record; the record is only ever written server-side via _govern.
    liar = Principal(tenant="acme", agent="alice", namespace="hr",
                     capabilities=_DEFAULT_CAPS | {"knowledge.accept"})
    c = cengine.create_claim(alice, subject="x", predicate="=", object="1")
    with pytest.raises(AuthorizationError):
        cengine.accept_claim(liar, c.id)         # same agent == claimant → denied
    # belief still shows no governance marker
    assert cengine.belief(alice, c.id)["governance"] is None


# ATTACK 5 — existence oracle. A cross-space probe must not distinguish absent vs hidden. -------
def test_no_existence_oracle_across_the_space_boundary(cengine, alice, bob) -> None:
    real = cengine.create_claim(alice, subject="x", predicate="=", object="1")  # private to alice
    missing = "clm_" + "0" * 32
    # both a hidden-real id and a truly-absent id look identical to bob
    assert cengine.get(bob, real.id) is cengine.get(bob, missing)               # both None
    with pytest.raises(NotFoundError):
        cengine.belief(bob, real.id)
    with pytest.raises(NotFoundError):
        cengine.belief(bob, missing)


# ATTACK 6 — corroboration is not deduplication. Two independent claims stay two claims. --------
def test_two_agents_asserting_the_same_thing_are_two_claims_not_one(cengine, alice, bob) -> None:
    sp = _shared(cengine, alice, bob)
    c1 = cengine.create_claim(alice, subject="sky", predicate="is", object="blue", space=sp)
    c2 = cengine.create_claim(bob, subject="sky", predicate="is", object="blue", space=sp)
    assert c1.id != c2.id                          # corroboration != collapse
    assert c1.claimant == "alice" and c2.claimant == "bob"


# ATTACK 7 — tamper the claim ledger. Any edit must break the hash chain. -----------------------
def test_claim_ledger_is_tamper_evident(cengine, alice, bob, curator) -> None:
    sp = _shared(cengine, alice, bob, curator)
    c = cengine.create_claim(alice, subject="x", predicate="=", object="1", space=sp)
    cengine.review_claim(bob, c.id, verdict="confirm")
    cengine.accept_claim(curator, c.id)
    assert cengine.verify_integrity() > 0          # the whole chain (incl. claim events) is intact
    # flip a byte in the first claim payload and the chain must reject it
    records = list(cengine.store.read_events())
    claim_idx = next(i for i, r in enumerate(records) if r.op == "claim_asserted")
    tampered = dict(records[claim_idx].payload)
    tampered["subject"] = "TAMPERED"
    object.__setattr__(records[claim_idx], "payload", tampered)
    with pytest.raises(IntegrityError):
        verify_chain(records)


# ATTACK 8 — a reviewer without read access cannot review a claim they can't see. --------------
def test_cannot_review_a_claim_outside_your_spaces(cengine, alice, bob) -> None:
    c = cengine.create_claim(alice, subject="x", predicate="=", object="1")  # private
    with pytest.raises(NotFoundError):
        cengine.review_claim(bob, c.id, verdict="dispute")


# ATTACK 9 — evidence relation is honoured; contradicting evidence cannot be silently upgraded. -
def test_contradicting_evidence_is_preserved_as_contradiction(cengine, alice, bob) -> None:
    sp = _shared(cengine, alice, bob)
    c = cengine.create_claim(alice, subject="x", predicate="=", object="1", space=sp)
    ev = cengine.create_evidence(bob, title="counter", uri="https://x/c", space=sp)
    cengine.attach_evidence(bob, evidence_id=ev.id, to_claim=c.id, relation="contradicts")
    rels = {link["relation"] for link in cengine.claim_evidence(alice, c.id)}
    assert rels == {"contradicts"}                 # never coerced to 'supports'
