"""ZERO_EGRESS_DEFAULT gate (checkpoint L). Measured, not assumed.

Every core operation runs while sockets are booby-trapped to raise on any attempt to
open a network connection. If the core made an implicit network call, these tests would
fail loudly.
"""

from __future__ import annotations

import socket

import pytest

from epistemos import Engine, Principal

pytestmark = pytest.mark.security


class NetworkAttempted(AssertionError):
    pass


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a, **k):
        raise NetworkAttempted("core attempted a network connection")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    if hasattr(socket, "socketpair"):
        monkeypatch.setattr(socket, "socketpair", boom)


def test_full_lifecycle_makes_no_network_calls(
    engine: Engine, ctx: Principal, no_network: None
) -> None:
    # startup already happened via fixture; exercise the whole surface under the net trap
    src = engine.add_source(ctx, uri="https://example.com/should-not-be-fetched", trust=0.5)
    obs = engine.observe(ctx, text="note", source=src.id)
    engine.ingest_document(ctx, title="doc", text="body", source=src.id)
    f = engine.assert_fact(ctx, subject="A", predicate="p", object="B",
                           source=src.id, derived_from=[obs.id])
    engine.supersede(ctx, f.id, new={"object": "C"})
    engine.confirm(ctx, engine.facts_for(ctx, subject="A", believed_only=True)[0].id, source=src.id)
    e1 = engine.add_entity(ctx, name="Alice")
    e2 = engine.add_entity(ctx, name="Acme")
    engine.add_relation(ctx, source_entity=e1.id, target_entity=e2.id, rel_type="x")
    engine.query_graph(ctx, e1.id)
    engine.record_decision(ctx, statement="d", evidence=[
        engine.facts_for(ctx, subject="A", believed_only=True)[0].id])
    engine.search(ctx, text="A p")
    engine.timeline(ctx, subject="A")
    engine.explain(ctx, f.id)
    engine.health(ctx, verify=True)
    dump = engine.export()
    engine.verify_integrity()
    # import path too
    from epistemos.storage import MemoryStore
    Engine(MemoryStore()).import_events(dump)


def test_source_uri_is_never_dereferenced(engine: Engine, ctx: Principal, no_network: None) -> None:
    # An SSRF-style URI is stored as an opaque identifier and never fetched.
    src = engine.add_source(ctx, uri="http://169.254.169.254/latest/meta-data/", trust=0.1)
    got = engine.get(ctx, src.id)
    assert got.uri == "http://169.254.169.254/latest/meta-data/"  # stored, not fetched
