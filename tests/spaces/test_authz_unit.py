"""EPISTEMOS-04: direct unit tests of the pure authorization decision (authz.can_read_object).

These exercise decision branches that the engine's store-level (tenant, namespace) pre-filtering
never reaches — the fail-closed defense-in-depth the read firewall depends on.
"""

from __future__ import annotations

from epistemos.authz import can_read_object
from epistemos.identity import Principal
from epistemos.spaces import Visibility

P = Principal(tenant="acme", agent="alice", namespace="hr")
ADMIN = Principal(tenant="acme", agent="root", namespace="hr",
                  capabilities=frozenset({"read", "admin"}))


def _obj(**kw):
    base = {"id": "o1", "tenant": "acme", "namespace": "hr", "owner": "alice", "spaces": ()}
    base.update(kw)
    return base


def _no_spaces(_sid):
    return None


def _no_members(_sid, _agent):
    return False


def test_cross_tenant_object_is_never_readable() -> None:
    # the fail-closed TENANT check (defense-in-depth even when the store already scopes)
    obj = _obj(tenant="globex")
    assert can_read_object(P, obj, space_of=_no_spaces, is_member=_no_members) is False


def test_private_object_readable_only_by_owner() -> None:
    assert can_read_object(P, _obj(owner="alice"),
                           space_of=_no_spaces, is_member=_no_members) is True
    assert can_read_object(P, _obj(owner="bob"),
                           space_of=_no_spaces, is_member=_no_members) is False


def test_private_object_owner_check_respects_namespace() -> None:
    assert can_read_object(P, _obj(owner="alice", namespace="finance"),
                           space_of=_no_spaces, is_member=_no_members) is False


def test_dangling_placement_grants_nothing() -> None:
    assert can_read_object(P, _obj(owner="bob", spaces=("spc_ghost",)),
                           space_of=_no_spaces, is_member=_no_members) is False


def test_team_space_requires_membership_or_ownership() -> None:
    def space_of(sid):
        return (Visibility.TEAM, "carol", "acme")  # owned by carol, not P

    assert can_read_object(P, _obj(owner="carol", spaces=("s",)),
                           space_of=space_of, is_member=_no_members) is False
    assert can_read_object(P, _obj(owner="carol", spaces=("s",)),
                           space_of=space_of, is_member=lambda s, a: a == "alice") is True


def test_org_space_is_tenant_wide() -> None:
    def space_of(sid):
        return (Visibility.ORGANIZATION, "carol", "acme")

    assert can_read_object(P, _obj(owner="carol", spaces=("s",)),
                           space_of=space_of, is_member=_no_members) is True


def test_org_space_in_another_tenant_is_not_readable() -> None:
    def space_of(sid):
        return (Visibility.PUBLIC, "carol", "globex")  # PUBLIC but in a different tenant

    assert can_read_object(P, _obj(owner="carol", spaces=("s",)),
                           space_of=space_of, is_member=_no_members) is False


def test_admin_overrides() -> None:
    assert can_read_object(ADMIN, _obj(owner="bob", spaces=("s",)),
                           space_of=_no_spaces, is_member=_no_members) is True
