"""EPISTEMOS-04: capability-based authorization + roles-are-capability-sets (§6-8, §22-23)."""

from __future__ import annotations

import pytest
from tests.spaces.conftest import principal

from epistemos import Engine, Principal
from epistemos.errors import AuthorizationError
from epistemos.identity import _DEFAULT_CAPS

# Roles are CONVENIENCE sets of capabilities — enforcement is by capability, never role name.
ROLES = {
    "VISITOR": frozenset({"knowledge.read", "space.read"}),
    "MEMBER": frozenset({"knowledge.read", "knowledge.search", "space.read"}),
    "CONTRIBUTOR": frozenset({"knowledge.read", "knowledge.contribute", "knowledge.share",
                              "space.read"}),
    "REVIEWER": frozenset({"knowledge.read", "knowledge.review", "claim.confirm",
                           "claim.dispute", "space.read"}),
    "CURATOR": frozenset({"knowledge.read", "knowledge.promote", "space.manage", "space.invite",
                          "space.read"}),
    "OWNER": frozenset({"knowledge.read", "knowledge.promote", "knowledge.retract",
                        "space.manage", "space.invite", "space.create", "space.read"}),
}


def _p(agent: str, role: str) -> Principal:
    return principal(agent, extra_caps=ROLES[role])


def test_default_caps_cannot_promote_toward_public(sengine: Engine, alice) -> None:
    """The default principal has NO promote capability — fail closed toward PUBLIC (§6)."""
    assert "knowledge.promote" not in _DEFAULT_CAPS
    assert "knowledge.share" not in _DEFAULT_CAPS
    sa = sengine.add_source(alice, uri="mem://a", trust=0.9)
    f = sengine.assert_fact(alice, subject="S", predicate="p", object="v", source=sa.id)
    org = sengine.create_space(alice, name="org", visibility="ORGANIZATION")
    with pytest.raises(AuthorizationError):
        sengine.promote(alice, f.id, into=org.id)


def test_curator_role_can_promote(sengine: Engine) -> None:
    curator = _p("cur", "CURATOR")
    sa = sengine.add_source(curator, uri="mem://a", trust=0.9)
    f = sengine.assert_fact(curator, subject="S", predicate="p", object="v", source=sa.id)
    org = sengine.create_space(curator, name="org", visibility="ORGANIZATION")
    sengine.promote(curator, f.id, into=org.id)  # allowed by capability, not role name


def test_role_is_only_a_capability_set_not_authority(sengine: Engine) -> None:
    """A principal whose *namespace* is 'owner' but who lacks the capability is still denied —
    authority is the capability, never a name (mission §7: no `if role == owner: allow`)."""
    fake_owner = Principal(tenant="acme", agent="owner", namespace="hr",
                           capabilities=frozenset({"read", "assert", "ingest", "space.create"}))
    sa = sengine.add_source(fake_owner, uri="mem://a", trust=0.9)
    f = sengine.assert_fact(fake_owner, subject="S", predicate="p", object="v", source=sa.id)
    pub = sengine.create_space(fake_owner, name="pub", visibility="PUBLIC")
    with pytest.raises(AuthorizationError):
        sengine.promote(fake_owner, f.id, into=pub.id)  # name 'owner' grants nothing


def test_agent_principal_is_subject_to_capabilities(sengine: Engine, alice) -> None:
    """§23: an agent principal gets no automatic exception — same capability gating."""
    hermes = Principal(tenant="acme", agent="hermes", namespace="hr",
                       capabilities=frozenset({"read", "knowledge.search"}))
    sa = sengine.add_source(alice, uri="mem://a", trust=0.9)
    f = sengine.assert_fact(alice, subject="S", predicate="p", object="v", source=sa.id)
    team = sengine.create_space(alice, name="team", visibility="TEAM")
    sengine.grant_capability(alice, space_id=team.id, agent="hermes")
    sengine.share(alice, f.id, into=team.id)
    assert sengine.get(hermes, f.id).object == "v"          # search: TEAM  -> allowed
    org = sengine.create_space(alice, name="org", visibility="ORGANIZATION")
    with pytest.raises(AuthorizationError):
        sengine.promote(hermes, f.id, into=org.id)          # promote: DENIED


def test_only_space_owner_manages_membership(sengine: Engine, alice, bob) -> None:
    space = sengine.create_space(alice, name="team", visibility="TEAM")
    # bob (not the owner, no space.manage) cannot grant himself membership
    with pytest.raises(AuthorizationError):
        sengine.grant_capability(bob, space_id=space.id, agent="bob")


def test_grant_revoke_are_ledger_events_and_rebuild(sengine: Engine, alice, bob) -> None:
    """Grants are projected state; a projection rebuild reproduces the exact access decision."""
    sa = sengine.add_source(alice, uri="mem://a", trust=0.9)
    f = sengine.assert_fact(alice, subject="S", predicate="p", object="v", source=sa.id)
    team = sengine.create_space(alice, name="team", visibility="TEAM")
    sengine.grant_capability(alice, space_id=team.id, agent="bob")
    sengine.share(alice, f.id, into=team.id)
    assert sengine.get(bob, f.id).object == "v"
    sengine.rebuild_projection()
    assert sengine.get(bob, f.id).object == "v"  # grant survives rebuild
    sengine.revoke_capability(alice, space_id=team.id, agent="bob")
    sengine.rebuild_projection()
    assert sengine.get(bob, f.id) is None  # revoke survives rebuild
