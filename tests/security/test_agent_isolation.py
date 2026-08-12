"""AGENT_ISOLATION gate (checkpoint H).

Within a shared namespace agents collaborate (shared reads) but cannot clobber each
other's writes (owner guard). Agent-private memory is achieved with a per-agent namespace.
An explicit ``admin`` capability can override the owner guard.
"""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal
from epistemos.errors import AuthorizationError, NotFoundError
from epistemos.identity import _DEFAULT_CAPS

pytestmark = pytest.mark.security

ALICE = Principal(tenant="acme", agent="alice", namespace="shared")
BOB = Principal(tenant="acme", agent="bob", namespace="shared")


def test_shared_namespace_allows_read(engine: Engine) -> None:
    f = engine.assert_fact(ALICE, subject="A", predicate="p", object="X")
    # Bob (same tenant/namespace) can read Alice's fact — shared knowledge.
    assert engine.get(BOB, f.id).object == "X"


def test_other_agent_cannot_clobber(engine: Engine) -> None:
    f = engine.assert_fact(ALICE, subject="A", predicate="p", object="X")
    with pytest.raises(AuthorizationError):
        engine.retract(BOB, f.id)
    with pytest.raises(AuthorizationError):
        engine.supersede(BOB, f.id, new={"object": "Y"})
    with pytest.raises(AuthorizationError):
        engine.correct_validity(BOB, f.id, valid_to="2026-02-01")


def test_other_agent_can_add_not_overwrite(engine: Engine) -> None:
    f = engine.assert_fact(ALICE, subject="A", predicate="p", object="X")
    # confirm and contradict are additive, allowed cross-agent
    s = engine.add_source(BOB, uri="mem://bob")
    engine.confirm(BOB, f.id, source=s.id)
    f2 = engine.assert_fact(BOB, subject="A", predicate="p", object="Z")
    engine.contradict(BOB, f.id, by=f2.id)  # allowed


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
