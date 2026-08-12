"""EPISTEMOS-04: Knowledge Space model + fail-closed visibility defaults (mission §3-5)."""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal
from epistemos.errors import AuthorizationError, ValidationError
from epistemos.spaces import KnowledgeSpace, Visibility, resolve_visibility

from tests.spaces.conftest import principal


def test_visibility_is_a_total_order() -> None:
    assert (Visibility.PRIVATE < Visibility.TEAM < Visibility.ORGANIZATION
            < Visibility.COMMUNITY < Visibility.PUBLIC)
    assert Visibility.PRIVATE == 0 and Visibility.PUBLIC == 4


@pytest.mark.parametrize("value,expected", [
    (None, Visibility.PRIVATE),           # absence -> PRIVATE, never PUBLIC
    ("TEAM", Visibility.TEAM),
    ("team", Visibility.TEAM),
    (2, Visibility.ORGANIZATION),
    (Visibility.PUBLIC, Visibility.PUBLIC),
])
def test_resolve_visibility_known(value, expected) -> None:
    assert resolve_visibility(value) is expected


@pytest.mark.parametrize("bad", ["", "SECRET", "public!", 99, -1, True, 1.5, object()])
def test_resolve_visibility_fails_closed(bad) -> None:
    # unknown/malformed raises rather than guessing (never defaults UP to PUBLIC)
    with pytest.raises(ValidationError):
        resolve_visibility(bad)


def test_space_kind_and_visibility_are_separate_fields() -> None:
    sp = KnowledgeSpace(id="spc_1", tenant="t", name="n", kind="TEAM",
                        visibility=Visibility.TEAM, owner="a", created_at="2026-01-01T00:00:00Z")
    d = sp.to_dict()
    assert d["space_kind"] == "TEAM" and d["visibility"] == 1 and d["kind"] == "space"
    assert KnowledgeSpace.from_dict(d).visibility is Visibility.TEAM


def test_create_space_requires_capability(sengine: Engine) -> None:
    no_create = Principal(tenant="acme", agent="a", namespace="hr",
                          capabilities=frozenset({"read"}))
    with pytest.raises(AuthorizationError):
        sengine.create_space(no_create, name="x", visibility="TEAM")


def test_create_space_rejects_unknown_visibility(sengine: Engine, alice: Principal) -> None:
    with pytest.raises(ValidationError):
        sengine.create_space(alice, name="x", visibility="SECRET")


def test_object_is_private_by_default(sengine: Engine, alice: Principal) -> None:
    f = sengine.assert_fact(alice, subject="A", predicate="p", object="v")
    stored = sengine.store.get_object(f.id)
    assert tuple(stored.get("spaces", ())) == ()  # empty == PRIVATE to owner (fail-closed default)


def test_space_is_scoped_to_its_tenant(sengine: Engine, alice: Principal) -> None:
    sp = sengine.create_space(alice, name="team", visibility="TEAM")
    other_tenant = principal("x", tenant="globex")
    assert sengine.get_space(other_tenant, sp.id) is None  # never visible cross-tenant


def test_create_space_defaults_kind_to_visibility_name(sengine: Engine, alice: Principal) -> None:
    sp = sengine.create_space(alice, name="team", visibility="ORGANIZATION")
    assert sp.kind == "ORGANIZATION" and sp.visibility is Visibility.ORGANIZATION
