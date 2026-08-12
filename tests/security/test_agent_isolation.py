"""AGENT_ISOLATION gate — updated for EPISTEMOS-04 Knowledge Spaces (was checkpoint H).

EPISTEMOS-04 corrects the v0.3 "shared namespace = shared reads" model (audit finding B-02:
namespace is a partition, not an authorization boundary). Now an object is **PRIVATE to its
owner by default**; another agent gains access only through an **explicit share into a space it
is granted**. Owner guards on clobbering writes are unchanged; ``admin`` still overrides.
"""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal
from epistemos.errors import AuthorizationError, NotFoundError
from epistemos.identity import _DEFAULT_CAPS

pytestmark = pytest.mark.security

ALICE = Principal(tenant="acme", agent="alice", namespace="shared")
BOB = Principal(tenant="acme", agent="bob", namespace="shared")


def test_private_by_default_not_readable_cross_agent(engine: Engine) -> None:
    f = engine.assert_fact(ALICE, subject="A", predicate="p", object="X")
    # EPISTEMOS-04: Bob canNOT read Alice's private fact (no implicit namespace sharing).
    assert engine.get(BOB, f.id) is None
    assert engine.search(BOB, text="X") == []


def test_explicit_share_grants_cross_agent_read(engine: Engine) -> None:
    f = engine.assert_fact(ALICE, subject="A", predicate="p", object="X")
    space = engine.create_space(ALICE, name="team", visibility="TEAM")
    engine.grant_capability(ALICE, space_id=space.id, agent="bob")
    engine.share(ALICE, f.id, into=space.id)
    # now Bob can read it — and only now
    assert engine.get(BOB, f.id).object == "X"
    engine.revoke_capability(ALICE, space_id=space.id, agent="bob")
    assert engine.get(BOB, f.id) is None  # revocation is immediate


def test_other_agent_cannot_clobber(engine: Engine) -> None:
    f = engine.assert_fact(ALICE, subject="A", predicate="p", object="X")
    with pytest.raises(AuthorizationError):
        engine.retract(BOB, f.id)
    with pytest.raises(AuthorizationError):
        engine.supersede(BOB, f.id, new={"object": "Y"})
    with pytest.raises(AuthorizationError):
        engine.correct_validity(BOB, f.id, valid_to="2026-02-01")


def test_shared_fact_allows_additive_cross_agent(engine: Engine) -> None:
    """confirm/contradict remain additive cross-agent — but only on a fact Bob can see."""
    f = engine.assert_fact(ALICE, subject="A", predicate="p", object="X")
    space = engine.create_space(ALICE, name="team", visibility="TEAM")
    engine.grant_capability(ALICE, space_id=space.id, agent="bob")
    engine.share(ALICE, f.id, into=space.id)
    s = engine.add_source(BOB, uri="mem://bob")
    engine.confirm(BOB, f.id, source=s.id)  # allowed now that Bob is in the space
    f2 = engine.assert_fact(BOB, subject="A", predicate="p", object="Z")
    engine.share(BOB, f2.id, into=space.id)
    engine.contradict(BOB, f.id, by=f2.id)  # allowed


def test_cannot_confirm_a_fact_you_cannot_see(engine: Engine) -> None:
    f = engine.assert_fact(ALICE, subject="A", predicate="p", object="X")
    s = engine.add_source(BOB, uri="mem://bob")
    with pytest.raises(NotFoundError):
        engine.confirm(BOB, f.id, source=s.id)  # Alice's fact is private to her


def test_agent_private_memory_via_namespace(engine: Engine) -> None:
    alice_priv = Principal(tenant="acme", agent="alice", namespace="agent:alice")
    bob_priv = Principal(tenant="acme", agent="bob", namespace="agent:bob")
    f = engine.assert_fact(alice_priv, subject="secret", predicate="p", object="v")
    # get() returns None for a foreign-scope id, indistinguishable from a truly absent id, so it
    # cannot be used as an existence oracle (EPISTEMOS-03, B-01). explain() still raises for both.
    assert engine.get(bob_priv, f.id) is None
    with pytest.raises(NotFoundError):
        engine.explain(bob_priv, f.id)
    assert engine.search(bob_priv, text="secret") == []


def test_admin_capability_overrides_owner_guard(engine: Engine) -> None:
    admin = Principal(tenant="acme", agent="root", namespace="shared",
                      capabilities=_DEFAULT_CAPS | {"admin"})
    f = engine.assert_fact(ALICE, subject="A", predicate="p", object="X")
    # admin may supersede another agent's fact
    engine.supersede(admin, f.id, new={"object": "Y"})
    assert engine.current(ALICE, subject="A", predicate="p") == "Y"
