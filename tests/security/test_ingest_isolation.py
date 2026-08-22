"""Compilation must not become a side channel.

`compile_document` reads the projection to decide what already exists (idempotence). Any read of
that kind is a place where one tenant can learn about another — through the returned data, or by
inference from what the system declines to create. These tests hold that boundary shut.
"""

from __future__ import annotations

import pytest

from epistemos.core import Engine
from epistemos.errors import NotFoundError
from epistemos.identity import Principal

pytestmark = pytest.mark.security

TEXT = "Owner: Alice Martins\nAlice Martins works at Acme.\n"


def _p(tenant: str, agent: str = "a", namespace: str = "kb") -> Principal:
    return Principal(tenant=tenant, agent=agent, namespace=namespace)


def test_a_document_in_another_tenant_is_not_compilable(store):
    """Not "forbidden" — invisible. Distinguishing the two would be an existence oracle."""
    engine = Engine(store)
    alice, mallory = _p("acme"), _p("evil")
    doc = engine.ingest_document(alice, title="Runbook", text=TEXT)

    with pytest.raises(NotFoundError):
        engine.compile_document(mallory, document=doc.id)


def test_compiling_in_one_tenant_creates_nothing_in_another(store):
    engine = Engine(store)
    alice, bob = _p("acme"), _p("globex")
    doc = engine.ingest_document(alice, title="Runbook", text=TEXT)
    engine.compile_document(alice, document=doc.id)

    assert list(engine.store.objects("globex", "kb", "claim")) == []
    assert list(engine.store.objects("globex", "kb", "evidence")) == []
    assert len(list(engine.store.objects("acme", "kb", "claim"))) > 0
    _ = bob


def test_idempotence_does_not_leak_across_tenants(store):
    """The dedupe key is content-derived, so two tenants compiling identical text would collide if
    the existing-key scan were not tenant-scoped. Each must get its own full set of claims."""
    engine = Engine(store)
    alice, bob = _p("acme"), _p("globex")
    doc_a = engine.ingest_document(alice, title="Runbook", text=TEXT)
    doc_b = engine.ingest_document(bob, title="Runbook", text=TEXT)

    first = engine.compile_document(alice, document=doc_a.id)
    second = engine.compile_document(bob, document=doc_b.id)

    assert first.created > 0
    # Bob must not be told "already present" for claims that exist only in Alice's tenant.
    assert second.created == first.created
    assert second.skipped == ()


def test_idempotence_does_not_leak_across_namespaces(store):
    engine = Engine(store)
    ops, hr = _p("acme", namespace="ops"), _p("acme", namespace="hr")
    doc_ops = engine.ingest_document(ops, title="Runbook", text=TEXT)
    doc_hr = engine.ingest_document(hr, title="Runbook", text=TEXT)

    first = engine.compile_document(ops, document=doc_ops.id)
    second = engine.compile_document(hr, document=doc_hr.id)

    assert second.created == first.created
    assert second.skipped == ()


def test_compilation_dereferences_nothing(store, monkeypatch):
    """Ingested text is inert data. A URI inside a document must never be fetched — the whole
    point of a zero-egress core is that hostile content cannot make it reach out."""
    import socket

    def explode(*args, **kwargs):  # pragma: no cover - the assertion is that this never runs
        raise AssertionError("compilation attempted a network connection")

    monkeypatch.setattr(socket, "socket", explode)
    monkeypatch.setattr(socket, "create_connection", explode)

    engine = Engine(store)
    ctx = _p("acme")
    hostile = (
        "Owner: Alice\n"
        "Callback: http://evil.example/steal\n"
        "See also: file:///etc/passwd\n"
        "Alice works at Acme.\n"
    )
    doc = engine.ingest_document(ctx, title="Runbook", text=hostile)
    result = engine.compile_document(ctx, document=doc.id)

    # The URI is captured verbatim as a *value*, never resolved.
    values = {c.object for c in result.claims}
    assert "http://evil.example/steal" in values


def test_compiled_claims_carry_the_compiling_agents_identity(store):
    engine = Engine(store)
    ctx = _p("acme", agent="compiler-bot")
    doc = engine.ingest_document(ctx, title="Runbook", text=TEXT)
    result = engine.compile_document(ctx, document=doc.id)

    for claim in result.claims:
        assert claim.owner == "compiler-bot"
        assert claim.tenant == "acme"
