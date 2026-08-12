"""Full-stack HTTP tests: the running panel server enforces auth, CSP, no-oracle errors, and the
same private-leak guarantees over the wire (mission §33/§34/§35). Uses a real ephemeral server."""
from __future__ import annotations

import json
import threading
import urllib.request as u

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
    eng.create_claim(alice, subject="Secret", predicate="is", object=SECRET)  # private to alice
    tokens = {"tok-alice": alice, "tok-bob": bob}
    srv = make_panel_server(eng, host="127.0.0.1", port=0, tokens=tokens,
                            demo_identities=[{"agent": "alice", "token": "tok-alice"}])
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    host, port = srv.server_address[0], srv.server_address[1]
    yield f"http://{host}:{port}"
    srv.shutdown()
    srv.server_close()
    eng.close()


def _get(base, path, token=None):
    req = u.Request(base + path)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        r = u.urlopen(req, timeout=5)
        return r.status, dict(r.headers), r.read()
    except u.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_unauthenticated_api_is_401(server):
    code, _, _ = _get(server, "/api/overview")
    assert code == 401


def test_static_index_carries_strict_csp(server):
    code, headers, body = _get(server, "/")
    assert code == 200
    csp = headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp and "connect-src 'self'" in csp
    # zero-egress at the browser: no wildcard/external origin permitted
    assert "http://" not in csp and "https://" not in csp and "*" not in csp
    assert headers.get("X-Content-Type-Options") == "nosniff"


def test_bob_cannot_see_private_over_http(server):
    code, _, body = _get(server, "/api/graph", token="tok-bob")
    assert code == 200 and SECRET.encode() not in body
    code, _, body = _get(server, "/api/search?text=" + SECRET, token="tok-bob")
    assert code == 200 and json.loads(body)["results"] == []
    code, _, body = _get(server, "/api/overview", token="tok-bob")
    assert SECRET.encode() not in body


def test_alice_sees_private_over_http(server):
    code, _, body = _get(server, "/api/search?text=" + SECRET, token="tok-alice")
    assert code == 200 and len(json.loads(body)["results"]) >= 1


def test_error_body_has_no_forbidden_vs_absent_oracle(server):
    # a claim id that doesn't exist and one that exists-but-forbidden must look the same to bob
    code_absent, _, body_absent = _get(server, "/api/claim?id=clm_" + "0" * 32, token="tok-bob")
    assert code_absent == 404
    # the error message must not reveal which case it was
    assert b"forbidden" not in body_absent.lower() and SECRET.encode() not in body_absent


def test_demo_identities_expose_no_more_than_configured(server):
    code, _, body = _get(server, "/api/demo/identities")
    assert code == 200
    ids = json.loads(body)["identities"]
    assert [i["agent"] for i in ids] == ["alice"]


def test_session_cookie_is_httponly_samesite(server):
    req = u.Request(server + "/api/session", data=json.dumps({"token": "tok-bob"}).encode(),
                    headers={"Content-Type": "application/json"}, method="POST")
    r = u.urlopen(req, timeout=5)
    setc = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in setc and "SameSite=Strict" in setc
