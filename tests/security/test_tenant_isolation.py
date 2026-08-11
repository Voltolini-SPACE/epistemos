"""TENANT_ISOLATION gate (checkpoint H). Fail-closed cross-tenant access.

Reads across a scope boundary raise NotFoundError (no existence leak); writes raise
TenantIsolationError/NotFoundError. Namespaces are the isolation boundary (agent-private
memory is a per-agent namespace).
"""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal
from epistemos.errors import IdentityError, NotFoundError, ValidationError

pytestmark = pytest.mark.security

A = Principal(tenant="acme", agent="a", namespace="hr")
B = Principal(tenant="globex", agent="b", namespace="hr")


def test_cross_tenant_read_is_notfound(engine: Engine) -> None:
    src = engine.add_source(A, uri="mem://s")
    f = engine.assert_fact(A, subject="Secret", predicate="p", object="V", source=src.id)
    with pytest.raises(NotFoundError):
        engine.get(B, f.id)
    with pytest.raises(NotFoundError):
        engine.explain(B, f.id)


def test_cross_tenant_search_and_timeline_isolated(engine: Engine) -> None:
    engine.assert_fact(A, subject="Secret", predicate="p", object="V")
    assert engine.search(B, text="Secret") == []
    assert engine.timeline(B, subject="Secret") == []
    assert engine.facts_for(B, subject="Secret") == []


def test_cross_tenant_write_denied(engine: Engine) -> None:
    f = engine.assert_fact(A, subject="Secret", predicate="p", object="V")
    with pytest.raises(NotFoundError):
        engine.retract(B, f.id)
    with pytest.raises(NotFoundError):
        engine.supersede(B, f.id, new={"object": "X"})
    with pytest.raises(NotFoundError):
        engine.confirm(B, f.id, source=engine.add_source(B, uri="mem://x").id)


def test_cross_tenant_graph_traversal_denied(engine: Engine) -> None:
    e1 = engine.add_entity(A, name="Alice")
    e2 = engine.add_entity(A, name="Acme")
    engine.add_relation(A, source_entity=e1.id, target_entity=e2.id, rel_type="works_at")
    with pytest.raises(NotFoundError):
        engine.query_graph(B, e1.id)
    with pytest.raises(NotFoundError):
        engine.neighbors(B, e1.id)


def test_namespace_isolation(engine: Engine) -> None:
    hr = Principal(tenant="acme", agent="a", namespace="hr")
    fin = Principal(tenant="acme", agent="a", namespace="finance")
    f = engine.assert_fact(hr, subject="Salary", predicate="p", object="100")
    with pytest.raises(NotFoundError):
        engine.get(fin, f.id)
    assert engine.search(fin, text="Salary") == []


def test_forged_context_rejected(engine: Engine) -> None:
    # non-Principal context
    with pytest.raises(IdentityError):
        engine.get(None, "fact_x")  # type: ignore[arg-type]
    with pytest.raises(IdentityError):
        engine.assert_fact("not-a-principal", subject="A", predicate="p")  # type: ignore[arg-type]
    # namespace traversal in the principal itself is rejected at construction
    with pytest.raises(ValidationError):
        Principal(tenant="acme", agent="a", namespace="../other")
    with pytest.raises(ValidationError):
        Principal(tenant="../etc", agent="a")
