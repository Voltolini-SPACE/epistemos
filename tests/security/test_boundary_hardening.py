"""EPISTEMOS-03 audit: the external boundaries must fail closed and not leak.

Findings B-01 (REST serves a None principal), B-06/B-07 (health leaks global counts),
B-03 boundaries (MCP crashes on a bad argument type), B-01 isolation (get() existence oracle).
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.api.rest import make_server
from epistemos.mcp import MCPServer
from epistemos.storage import SQLiteStore

A = Principal(tenant="acme", agent="alice", namespace="hr")
G = Principal(tenant="globex", agent="g", namespace="hr")


@pytest.fixture
def eng(tmp_path) -> Engine:
    e = Engine(SQLiteStore(tmp_path / "b.db"), clock=ManualClock())
    s = e.add_source(A, uri="mem://a", trust=0.9)
    e.assert_fact(A, subject="X", predicate="p", object="secretvalue", source=s.id)
    return e


def _serve(eng: Engine, auth) -> Iterator[int]:
    srv = make_server(eng, auth=auth)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield port
    finally:
        srv.shutdown()
        srv.server_close()


def _get(port: int, path: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="GET")
    req.add_header("Authorization", "Bearer tok")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_rest_fails_closed_when_authresolver_returns_none(eng: Engine) -> None:
    """B-01: an AuthResolver that returns None (instead of raising) must not yield a full dump."""
    def bad_auth(headers):  # returns None rather than raising — a plausible plugin bug
        return None

    for port in _serve(eng, bad_auth):
        status, payload = _get(port, "/export")
        assert status in (401, 500)
        assert "secretvalue" not in json.dumps(payload), "None principal produced a full export"


def test_health_does_not_leak_global_counts_to_a_principal(eng: Engine) -> None:
    """B-06/B-07: a principal's health must not reveal store-global write activity."""
    # globex asks health; acme's events must not be counted for it, and the global chain head
    # (which reveals that writes happened) must not be exposed to a scoped caller.
    h = eng.health(G)
    assert h["event_count"] == 0, "health leaked another tenant's event count"
    assert h.get("head_hash") is None, "health exposed the global chain head to a scoped caller"
    # the owner sees its own scoped activity
    ha = eng.health(A)
    assert ha["event_count"] >= 2
    # the operator (no principal) still gets the global view
    op = eng.health()
    assert op["event_count"] >= 2 and op["head_hash"] is not None


def test_get_is_not_an_existence_oracle(eng: Engine) -> None:
    """B-01 isolation: get() must not distinguish 'absent' from 'exists in another scope'."""
    real_id = next(o["id"] for o in eng.store.objects(A.tenant, A.namespace, kind="fact"))
    # a completely absent id and a real-but-foreign id must be indistinguishable to globex
    assert eng.get(G, real_id) is None
    assert eng.get(G, "fact_deadbeef" + "0" * 24) is None
    # the owner still gets its object
    assert eng.get(A, real_id).object == "secretvalue"


def test_mcp_does_not_crash_on_bad_argument_type(eng: Engine) -> None:
    """B-03 boundaries: a malformed argument must be a tool error, not an uncaught exception."""
    srv = MCPServer(eng, A)
    resp = srv.handle({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "assert_fact",
                   "arguments": {"subject": "S", "predicate": "p", "confidence": "not-a-number"}},
    })
    assert resp is not None
    assert "error" not in resp, "a bad argument crashed the JSON-RPC layer"
    assert resp["result"]["isError"] is True
    # the server is still alive and serves a good call afterwards
    ok = srv.handle({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "current", "arguments": {"subject": "X", "predicate": "p"}},
    })
    assert ok["result"]["isError"] is False
