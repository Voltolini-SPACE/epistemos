"""MCP_BOUNDARY gate (checkpoint W). MCP as a hostile frontier."""

from __future__ import annotations

import json

import pytest

from epistemos import Engine, Principal
from epistemos.mcp import TOOLS, MCPServer
from epistemos.storage import MemoryStore

pytestmark = pytest.mark.integration


@pytest.fixture
def mcp() -> MCPServer:
    engine = Engine(MemoryStore())
    return MCPServer(engine, Principal(tenant="acme", agent="mcp", namespace="default"))


def _call(mcp: MCPServer, name: str, args: dict) -> dict:
    resp = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": args}})
    return resp


def test_initialize_and_list(mcp: MCPServer) -> None:
    init = mcp.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}})
    assert init["result"]["protocolVersion"]
    listing = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {t["name"] for t in listing["result"]["tools"]}
    # safe tools present
    assert {"assert_fact", "current", "search", "explain"} <= names
    # NO generic power tools exposed
    for forbidden in ("execute", "eval", "query_raw_sql", "query_raw_cypher",
                      "filesystem_read", "url_fetch", "shell"):
        assert forbidden not in names and forbidden not in TOOLS


def test_notification_returns_nothing(mcp: MCPServer) -> None:
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_assert_and_current_roundtrip(mcp: MCPServer) -> None:
    r = _call(mcp, "assert_fact", {"subject": "Alice", "predicate": "works_at", "object": "Acme"})
    assert r["result"]["isError"] is False
    r2 = _call(mcp, "current", {"subject": "Alice", "predicate": "works_at"})
    payload = json.loads(r2["result"]["content"][0]["text"])
    assert payload["value"] == "Acme"


def test_unknown_tool_is_protocol_error(mcp: MCPServer) -> None:
    r = _call(mcp, "execute", {"cmd": "rm -rf /"})
    assert r["error"]["code"] == -32602


def test_unknown_method_is_error(mcp: MCPServer) -> None:
    r = mcp.handle({"jsonrpc": "2.0", "id": 9, "method": "os/exec"})
    assert r["error"]["code"] == -32601


def test_client_cannot_escalate_tenant(mcp: MCPServer) -> None:
    # A malicious 'tenant'/'namespace' argument is ignored: identity is server-side.
    _call(mcp, "assert_fact", {"subject": "X", "predicate": "p", "object": "Y",
                               "tenant": "victim", "namespace": "secret"})
    # the fact landed in the server principal's scope (acme/default), not 'victim'
    victim_view = MCPServer(Engine(mcp.engine.store),  # same underlying store
                            Principal(tenant="victim", agent="x", namespace="secret"))
    r = _call(victim_view, "current", {"subject": "X", "predicate": "p"})
    assert json.loads(r["result"]["content"][0]["text"])["value"] is None
    # and it IS visible in the real acme scope
    r2 = _call(mcp, "current", {"subject": "X", "predicate": "p"})
    assert json.loads(r2["result"]["content"][0]["text"])["value"] == "Y"


def test_injection_payload_is_inert(mcp: MCPServer) -> None:
    poison = "'; DROP TABLE objects; -- MATCH (n) DETACH DELETE n"
    r = _call(mcp, "assert_fact", {"subject": poison, "predicate": "p", "object": "v"})
    assert r["result"]["isError"] is False
    r2 = _call(mcp, "current", {"subject": poison, "predicate": "p"})
    assert json.loads(r2["result"]["content"][0]["text"])["value"] == "v"


def test_domain_error_is_tool_error_not_crash(mcp: MCPServer) -> None:
    r = _call(mcp, "explain", {"id": "fact_does_not_exist"})
    assert r["result"]["isError"] is True


def test_missing_required_arg_is_tool_error(mcp: MCPServer) -> None:
    r = _call(mcp, "assert_fact", {"subject": "A"})  # missing predicate
    assert r["result"]["isError"] is True
