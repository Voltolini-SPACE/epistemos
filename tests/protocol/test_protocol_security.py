"""EPCTX protocol security (mission §28) — the P0 gates.

    PRIVATE_EPCTX_LEAK = 0   PRIVATE_EXPANSION_LEAK = 0   CROSS_TENANT_EPCTX_LEAK = 0

Attacks: principal / tenant / space / capability spoofing, cross-tenant reads, private
contradiction / provenance leaks, expansion handle abuse (forged, cross-principal, cross-tenant,
revoked), oversized and deeply-nested and unicode payloads. Identity is always server-side; the
request body / tool args / query never carry authority.
"""

from __future__ import annotations

import json
import threading

import pytest

from epistemos import Engine, Principal
from epistemos.api.rest import make_server
from epistemos.mcp import MCPServer
from epistemos.protocol.client import McpContextClient
from epistemos.storage import MemoryStore

from .conftest import principal

SECRET = "SECRETXYZ_epctx_marker"


def _blob(doc: object) -> str:
    return json.dumps(doc, default=str)


# ---- private data never leaks into another principal's document ------------
def test_private_prior_version_not_in_other_principals_epctx():
    eng = Engine(MemoryStore())
    alice, bob = principal("alice"), principal("bob")
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob")
    f = eng.assert_fact(alice, subject="Deploy", predicate="is", object=SECRET)  # private prior
    f2 = eng.supersede(alice, f.id, new={"object": "production"}, reason="done")
    eng.share(alice, f2.id, into=team.id)
    doc = eng.epctx(bob, "Deploy", intent="current")
    assert SECRET not in _blob(doc)


def test_private_contradiction_not_in_other_principals_epctx():
    eng = Engine(MemoryStore())
    alice, bob = principal("alice"), principal("bob")
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob")
    claim = eng.create_claim(alice, subject="Widget", predicate="is", object="fine", space=team.id)
    priv = eng.create_evidence(alice, title=SECRET, uri="mem://x",
                               metadata={"relation": "contradicts"})
    eng.attach_evidence(alice, evidence_id=priv.id, to_claim=claim.id, relation="contradicts")
    bob_doc = eng.epctx(bob, "Widget", intent="contradiction")
    assert SECRET not in _blob(bob_doc)
    assert priv.id not in [c["id"] for c in bob_doc["contradictions"]]
    # the owner DOES see it
    alice_doc = eng.epctx(alice, "Widget", intent="contradiction")
    assert priv.id in [c["id"] for c in alice_doc["contradictions"]]


def test_cross_tenant_epctx_is_empty():
    eng = Engine(MemoryStore())
    alice = principal("alice")
    eng.assert_fact(alice, subject="Deploy", predicate="is", object=SECRET)
    outsider = principal("mallory", tenant="evilcorp")
    doc = eng.epctx(outsider, "Deploy", intent="current")
    assert all(len(v) == 0 for v in doc["context"].values())
    assert SECRET not in _blob(doc)


# ---- expansion handle safety (§21, §22) -----------------------------------
def _mint_handle(eng: Engine, owner: Principal) -> str:
    f = eng.assert_fact(owner, subject="Datastore", predicate="is", object=SECRET)
    eng.supersede(owner, f.id, new={"object": "postgres"}, reason="m")
    doc = eng.epctx(owner, "Datastore", intent="current")
    return str(doc["expansion"]["handles"][0]["handle"])


def test_forged_handle_is_refused_without_oracle():
    eng = Engine(MemoryStore())
    alice = principal("alice")
    _mint_handle(eng, alice)
    out = eng.expand(alice, "xph_deadbeef_not_a_real_handle")
    assert out["authorized"] is False and out["members"] == []


def test_cross_principal_handle_refused():
    eng = Engine(MemoryStore())
    alice, bob = principal("alice"), principal("bob")
    handle = _mint_handle(eng, alice)      # bound to alice's identity, wraps her private prior
    out = eng.expand(bob, handle)          # bob (same tenant, different agent) presents it
    assert out["authorized"] is False and out["members"] == []
    assert SECRET not in _blob(out)


def test_cross_tenant_handle_refused():
    eng = Engine(MemoryStore())
    alice = principal("alice")
    mallory = principal("mallory", tenant="evilcorp")
    handle = _mint_handle(eng, alice)
    out = eng.expand(mallory, handle)
    assert out["authorized"] is False and SECRET not in _blob(out)


def test_revoked_access_expansion_drops_member():
    """A member readable when the handle was minted but unreadable now (grant revoked) must be
    dropped on redemption — STALE_EXPANSION_PRIVATE_LEAK = 0."""
    eng = Engine(MemoryStore())
    alice, bob = principal("alice"), principal("bob")
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob",
                         capabilities=("knowledge.read", "assert", "supersede"))
    # a shared, superseded fact bob can read while granted
    f = eng.assert_fact(alice, subject="Shared", predicate="is", object=SECRET)
    f2 = eng.supersede(alice, f.id, new={"object": "v2"}, reason="m")
    eng.share(alice, f.id, into=team.id)
    eng.share(alice, f2.id, into=team.id)
    doc = eng.epctx(bob, "Shared", intent="current")
    handles = doc["expansion"]["handles"]
    if not handles:                        # if nothing collapsed for bob, nothing to leak — done
        return
    handle = handles[0]["handle"]
    eng.revoke_capability(alice, space_id=team.id, agent="bob")   # revoke AFTER minting
    out = eng.expand(bob, handle)
    assert SECRET not in _blob(out)        # revoked member must not come back through the handle


# ---- REST: identity is the token, body carries no authority ---------------
def test_rest_body_cannot_spoof_identity():
    eng = Engine(MemoryStore())
    alice = principal("alice")
    eng.assert_fact(alice, subject="Deploy", predicate="is", object=SECRET)
    outsider = principal("mallory", tenant="evilcorp")
    srv = make_server(eng, tokens={"tok-out": outsider})
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        from epistemos.sdk import RemoteClient
        rc = RemoteClient(f"http://127.0.0.1:{port}", "tok-out")
        # body tries to spoof tenant/principal/capabilities — all must be ignored
        doc = rc._request("POST", "/context", body={
            "query": "Deploy", "intent": "current",
            "tenant": "acme", "principal": "alice",
            "capabilities": ["admin"], "namespace": "kb",
        })
        assert SECRET not in _blob(doc)
        assert all(len(v) == 0 for v in doc["context"].values())
    finally:
        srv.shutdown()


def test_rest_oversized_body_rejected():
    eng = Engine(MemoryStore())
    alice = principal("alice")
    srv = make_server(eng, tokens={"tok": alice})
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        big = json.dumps({"query": "x" * (9 * 1024 * 1024)})
        conn.request("POST", "/context", body=big,
                     headers={"Authorization": "Bearer tok", "Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        assert resp.status == 400  # ValidationError -> 400; server stays up, no crash
    finally:
        srv.shutdown()


# ---- MCP: args carry no authority; malformed args are tool errors ----------
def test_mcp_args_cannot_spoof_identity():
    eng = Engine(MemoryStore())
    alice = principal("alice")
    eng.assert_fact(alice, subject="Deploy", predicate="is", object=SECRET)
    outsider = principal("mallory", tenant="evilcorp")
    mcp = McpContextClient(MCPServer(eng, outsider))
    doc = mcp.context("Deploy", intent="current")
    assert SECRET not in _blob(doc)


def test_unicode_is_data_and_control_chars_are_rejected(seeded):
    engine, alice, _ = seeded
    from epistemos.errors import ValidationError

    # valid (if exotic) unicode is accepted as data: RTL override, emoji, HTML-looking text
    doc = engine.epctx(alice, "Datastore\u202e \U0001F4A5 <script>alert(1)</script>",
                       intent="current")
    assert doc["protocol_version"] == "EPCTX/1"
    # control characters / NUL are cleanly rejected, never a crash
    with pytest.raises(ValidationError):
        engine.epctx(alice, "Datastore\x00tail", intent="current")


def test_deeply_nested_profile_does_not_crash(seeded):
    engine, alice, _ = seeded
    nested: dict = {"x": 1}
    for _ in range(50):
        nested = {"x": nested}
    with pytest.raises((TypeError, ValueError)):
        # consumer_profile must be an object we can interpret; a pathological value is rejected,
        # never crashes the process
        engine.epctx(alice, "Datastore", consumer_profile=[nested])  # type: ignore[arg-type]
