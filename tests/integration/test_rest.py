"""REST_BOUNDARY gate (checkpoint V) + RemoteClient half of PYTHON_SDK (X).

A real localhost HTTP server over a real socket. The REST layer is a thin adapter: auth is
pluggable, identity comes from the token (not the body), and cross-tenant is impossible.
"""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator

import pytest

from epistemos import Engine, Principal
from epistemos.api.rest import make_server
from epistemos.sdk import RemoteClient
from epistemos.storage import MemoryStore

pytestmark = pytest.mark.integration

TOKENS = {
    "tok-acme": Principal(tenant="acme", agent="rest", namespace="default"),
    "tok-globex": Principal(tenant="globex", agent="rest", namespace="default"),
}


@pytest.fixture
def server() -> Iterator[str]:
    engine = Engine(MemoryStore())
    srv = make_server(engine, tokens=TOKENS)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    # default bind is localhost only
    assert srv.server_address[0] == "127.0.0.1"
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    engine.close()


def _raw(base: str, method: str, path: str, *, token: str | None = None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", int(base.rsplit(":", 1)[1]), timeout=5)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    conn.request(method, path, body=json.dumps(body) if body else None, headers=headers)
    resp = conn.getresponse()
    data = json.loads(resp.read() or b"{}")
    conn.close()
    return resp.status, data


def test_health_requires_auth(server: str) -> None:
    status, data = _raw(server, "GET", "/health")
    assert status == 401 and data["error"] == "IdentityError"
    status, data = _raw(server, "GET", "/health", token="tok-acme")
    assert status == 200 and data["event_count"] == 0


def test_bad_token_rejected(server: str) -> None:
    status, _ = _raw(server, "GET", "/health", token="tok-nope")
    assert status == 401


def test_assert_and_current_via_remote_client(server: str) -> None:
    c = RemoteClient(server, "tok-acme")
    sid = c.add_source(uri="mem://s", trust=0.8)
    fid = c.assert_fact(subject="Alice", predicate="works_at", object="Acme", source=sid)
    assert fid.startswith("fact_")
    assert c.current(subject="Alice", predicate="works_at") == "Acme"
    res = c.search(text="Alice works")
    assert res and "why_returned" in res[0]


def test_identity_comes_from_token_not_body(server: str) -> None:
    acme = RemoteClient(server, "tok-acme")
    globex = RemoteClient(server, "tok-globex")
    acme.assert_fact(subject="Secret", predicate="p", object="V")
    # globex cannot see acme's data — even though it hits the same server/process
    assert globex.current(subject="Secret", predicate="p") is None
    assert globex.search(text="Secret") == []


def test_validation_error_maps_to_400(server: str) -> None:
    status, data = _raw(server, "POST", "/facts", token="tok-acme",
                        body={"subject": "A", "predicate": "p", "object": "B",
                              "valid_from": "not-a-date"})
    assert status == 400 and data["error"] == "ValidationError"


def test_remote_client_maps_errors(server: str) -> None:
    from epistemos.errors import IdentityError, ValidationError

    with pytest.raises(IdentityError):
        RemoteClient(server, "bad-token").health()
    with pytest.raises(ValidationError):
        RemoteClient(server, "tok-acme").assert_fact(subject="A", predicate="p",
                                                     object="B", valid_from="nope")
