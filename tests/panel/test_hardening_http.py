"""Hardening regressions over the wire (EPISTEMOS-PANEL-HARDENING-01).

Adversarial HTTP tests that pin the fixes for:

* **F1** malformed / missing query & body params must be **400** with a SAFE message, never a
  **500** echoing a raw Python error (``invalid literal for int()``, ``'id'``);
* **F3** an errored POST must not leave its body on a keep-alive socket to be re-parsed as a
  smuggled request (HTTP desync);
* **F4** the ``Server`` header must not advertise the Python runtime version;

plus the auth/oracle/SSE invariants at the HTTP layer.
"""
from __future__ import annotations

import http.client
import json
import socket
import threading

import pytest
from tests.panel.conftest import SECRET, principal

from epistemos import Engine
from epistemos.api.server import make_panel_server
from epistemos.storage import MemoryStore


@pytest.fixture
def server():
    eng = Engine(MemoryStore())
    alice = principal("alice", extra=frozenset({"knowledge.share"}))
    bob = principal("bob")
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob")
    eng.create_claim(alice, subject="Shared", predicate="is", object="visible", space=team.id)
    secret = eng.create_claim(alice, subject="Secret", predicate="is", object=SECRET)
    tokens = {"tok-alice": alice, "tok-bob": bob}
    srv = make_panel_server(eng, host="127.0.0.1", port=0, tokens=tokens)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    host, port = srv.server_address[0], srv.server_address[1]
    yield host, port, secret.id
    srv.shutdown()
    srv.server_close()
    eng.close()


def _get(host, port, path, token=None):
    c = http.client.HTTPConnection(host, port, timeout=5)
    hdrs = {"Authorization": f"Bearer {token}"} if token else {}
    c.request("GET", path, headers=hdrs)
    r = c.getresponse()
    body = r.read()
    st, headers = r.status, dict(r.getheaders())
    c.close()
    return st, headers, body


def _post(host, port, path, body, token=None):
    c = http.client.HTTPConnection(host, port, timeout=5)
    hdrs = {"Content-Type": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    data = body if isinstance(body, (bytes, str)) else json.dumps(body)
    c.request("POST", path, body=data, headers=hdrs)
    r = c.getresponse()
    out = r.read()
    st = r.status
    c.close()
    return st, out


_PYTHON_INTERNALS = (b"Traceback", b"invalid literal", b"KeyError", b'File "', b"line ")


# ---- F1: malformed / missing params -> 400 with a safe message (never 500 + internals) ----
@pytest.mark.parametrize("path", [
    "/api/graph?hops=abc",
    "/api/graph?limit=xyz",
    "/api/list?kind=claim&offset=abc",
    "/api/activity?since=NaN",
    "/api/claim",            # missing id
    "/api/belief",           # missing id
    "/api/evidence",         # missing id
    "/api/explain",          # missing id
    "/api/graph/expand",     # missing node
    "/api/asof",             # missing at
])
def test_malformed_param_is_400_not_500(server, path):
    host, port, _ = server
    st, _, body = _get(host, port, path, token="tok-alice")
    assert st == 400, f"{path} -> {st} (want 400)"
    assert not any(tok in body for tok in _PYTHON_INTERNALS), body[:120]
    # the safe message names the parameter, never leaks the Python exception text
    assert b"int()" not in body and b"literal" not in body


def test_search_post_bad_limit_is_400(server):
    host, port, _ = server
    st, body = _post(host, port, "/api/search", {"text": "x", "limit": "abc"}, token="tok-alice")
    assert st == 400 and not any(t in body for t in _PYTHON_INTERNALS)


def test_valid_bounds_still_clamp_not_error(server):
    # negative and huge limits are clamped by the read-model, not rejected as errors
    host, port, _ = server
    for path in ("/api/graph?limit=-5", "/api/graph?limit=999999999"):
        st, _, _ = _get(host, port, path, token="tok-alice")
        assert st == 200, f"{path} -> {st}"


# ---- F3: no request smuggling via an undrained POST body ----
def test_errored_post_body_is_not_smuggled(server):
    host, port, _ = server
    # POST that fails auth (no token) BEFORE its body is read; the body is a full smuggled request.
    s = socket.create_connection((host, port), timeout=5)
    smuggled = (b"GET /api/overview HTTP/1.1\r\nHost: x\r\n"
                b"Authorization: Bearer tok-alice\r\n\r\n")
    s.sendall(b"POST /api/search HTTP/1.1\r\nHost: x\r\nContent-Length: "
              + str(len(smuggled)).encode() + b"\r\n\r\n" + smuggled)
    s.settimeout(2.0)
    data = b""
    try:
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
            if len(data) > 200_000:
                break
    except TimeoutError:
        pass
    s.close()
    # exactly ONE response; the smuggled GET must not have executed as a second request
    assert data.count(b"HTTP/1.") <= 1, f"smuggled request executed: {data[:200]!r}"
    assert SECRET.encode() not in data


def test_bad_json_body_does_not_hang_and_is_400(server):
    # a body that is read but fails JSON parsing must still 400 cleanly (no double-drain hang)
    host, port, _ = server
    st, body = _post(host, port, "/api/search", b"{not json", token="tok-alice")
    assert st == 400 and not any(t in body for t in _PYTHON_INTERNALS)


def test_oversized_body_is_rejected_without_500(server):
    host, port, _ = server
    c = http.client.HTTPConnection(host, port, timeout=4)
    try:
        c.request("POST", "/api/search", body=b'{"text":"' + b"A" * 1_100_000 + b'"}',
                  headers={"Content-Type": "application/json", "Authorization": "Bearer tok-alice"})
        st = c.getresponse().status
    except (BrokenPipeError, ConnectionResetError, TimeoutError,
            http.client.RemoteDisconnected, OSError):
        st = -1  # server closed the connection instead of reading gigabytes — an acceptable reject
    finally:
        c.close()
    assert st in (400, 413, -1), f"oversized body -> {st}"


# ---- F4: Server header does not advertise the Python version ----
def test_server_header_hides_python_version(server):
    host, port, _ = server
    _, headers, _ = _get(host, port, "/", token=None)
    server_hdr = headers.get("Server", "")
    assert "epistemos-panel" in server_hdr
    assert "Python/" not in server_hdr, server_hdr


def test_no_cors_header_same_origin_only(server):
    # the panel is same-origin by design — it must not advertise a cross-origin allowance
    host, port, _ = server
    _, headers, _ = _get(host, port, "/api/counts", token="tok-alice")
    assert "Access-Control-Allow-Origin" not in headers
    assert "Access-Control-Allow-Credentials" not in headers


# ---- auth / oracle / SSE at the HTTP layer ----
@pytest.mark.parametrize("token", ["nope", "tok-alic", "' OR '1'='1", "A" * 4000])
def test_bad_tokens_are_rejected(server, token):
    host, port, _ = server
    st, _, body = _get(host, port, "/api/overview", token=token)
    assert st in (401, 431)  # 401 unauthorized, or 431 for an oversized header — both reject
    assert SECRET.encode() not in body


def test_no_forbidden_vs_absent_oracle(server):
    host, port, secret_id = server
    st_absent, _, b_absent = _get(host, port, f"/api/claim?id=clm_{'0'*32}", token="tok-bob")
    st_forbidden, _, b_forbidden = _get(host, port, f"/api/claim?id={secret_id}", token="tok-bob")
    assert st_absent == st_forbidden == 404
    assert b"forbidden" not in b_forbidden.lower() and SECRET.encode() not in b_forbidden


def test_sse_requires_auth(server):
    host, port, _ = server
    st, _, _ = _get(host, port, "/api/stream", token=None)
    assert st == 401
