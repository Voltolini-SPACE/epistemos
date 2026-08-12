"""Shared fixtures for the EPCTX protocol tests."""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest

from epistemos import Engine, Principal
from epistemos.api.rest import make_server
from epistemos.identity import _DEFAULT_CAPS
from epistemos.mcp import MCPServer
from epistemos.protocol.client import LocalContextClient, McpContextClient, RestContextClient
from epistemos.storage import MemoryStore

CAPS = _DEFAULT_CAPS | frozenset({"supersede", "decide", "knowledge.share", "space.create"})


def principal(agent: str = "alice", tenant: str = "acme") -> Principal:
    return Principal(tenant=tenant, agent=agent, namespace="kb", capabilities=CAPS)


def seed(engine: Engine, p: Principal) -> dict[str, str]:
    """A small corpus: a superseded fact (history), a disputed claim, a decision, duplicates."""
    ids: dict[str, str] = {}
    f = engine.assert_fact(p, subject="Datastore", predicate="is", object="mongo")
    f = engine.supersede(p, f.id, new={"object": "postgres"}, reason="migration")
    ids["fact_current"] = f.id
    c = engine.create_claim(p, subject="Revenue", predicate="grew", object="yes")
    ev = engine.create_evidence(p, title="revenue fell in Q3", uri="mem://q3",
                                metadata={"relation": "contradicts"})
    engine.attach_evidence(p, evidence_id=ev.id, to_claim=c.id, relation="contradicts")
    ids["claim"], ids["contra"] = c.id, ev.id
    be = engine.create_evidence(p, title="benchmark strong", uri="mem://bench",
                                metadata={"relation": "supports"})
    d = engine.record_decision(p, statement="Adopt Postgres", evidence=[be.id])
    ids["decision"] = d.id
    return ids


@pytest.fixture
def engine() -> Engine:
    return Engine(MemoryStore())


@pytest.fixture
def alice() -> Principal:
    return principal("alice")


@pytest.fixture
def seeded(engine: Engine, alice: Principal) -> tuple[Engine, Principal, dict[str, str]]:
    ids = seed(engine, alice)
    return engine, alice, ids


@pytest.fixture
def rest_server(engine: Engine, alice: Principal) -> Iterator[tuple[str, str]]:
    srv = make_server(engine, tokens={"tok-alice": alice})
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}", "tok-alice"
    finally:
        srv.shutdown()


def clients(engine: Engine, alice: Principal, rest: tuple[str, str]
            ) -> dict[str, object]:
    return {
        "local": LocalContextClient(engine, alice),
        "rest": RestContextClient(rest[0], rest[1]),
        "mcp": McpContextClient(MCPServer(engine, alice)),
    }
