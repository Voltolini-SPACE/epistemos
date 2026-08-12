"""EPISTEMOS-03 audit: export must not cross the tenant boundary.

Finding A-11 (CRITICAL) — ``Engine.export()`` takes no principal and returns the *whole*
multi-tenant ledger. The REST route ``GET /export`` forwarded it to any authenticated caller,
so a token for tenant B could read tenant A's complete history, including facts, sources and
document text. That defeats the fail-closed multi-tenant invariant at the external boundary.

Finding A-06 (MEDIUM) — ``health()`` reported ``integrity_ok: True`` without having verified
anything, so a corrupted ledger looked healthy.
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
from epistemos.errors import AuthorizationError
from epistemos.storage import SQLiteStore

A = Principal(tenant="acme", agent="claude", namespace="hr")
B = Principal(tenant="globex", agent="rival", namespace="secret")
SECRET = "ACMECONFIDENTIAL777"


@pytest.fixture
def two_tenant_engine(tmp_path) -> Iterator[Engine]:
    eng = Engine(SQLiteStore(tmp_path / "x.db"), clock=ManualClock())
    sa = eng.add_source(A, uri="mem://a", trust=0.9)
    eng.assert_fact(A, subject="Alice", predicate="salary", object=SECRET, source=sa.id)
    sb = eng.add_source(B, uri="mem://b", trust=0.9)
    eng.assert_fact(B, subject="Bob", predicate="role", object="engineer", source=sb.id)
    yield eng
    eng.close()


def _serve(eng: Engine) -> Iterator[int]:
    srv = make_server(eng, tokens={"tokA": A, "tokB": B})
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield port
    finally:
        srv.shutdown()
        srv.server_close()


def _get(port: int, path: str, token: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_rest_export_does_not_leak_other_tenants(two_tenant_engine: Engine) -> None:
    """A-11: tenant B must never receive tenant A's data from /export."""
    for port in _serve(two_tenant_engine):
        status, payload = _get(port, "/export", "tokB")
        assert status == 200, payload
        blob = json.dumps(payload)
        assert SECRET not in blob, "acme's confidential fact leaked to globex"
        tenants = {e.get("tenant") for e in payload.get("events", [])}
        assert tenants <= {B.tenant}, f"export contained foreign tenants: {tenants}"


def test_scoped_export_is_self_consistent_and_importable(two_tenant_engine: Engine,
                                                         tmp_path) -> None:
    """A scope-limited export must still be a valid, verifiable, importable ledger."""
    payload = two_tenant_engine.export(B)
    assert {e["tenant"] for e in payload["events"]} == {B.tenant}
    target = Engine(SQLiteStore(tmp_path / "imported.db"), clock=ManualClock())
    n = target.import_events(payload, verify=True)
    assert n == payload["event_count"]
    target.verify_integrity()
    assert target.as_of(B, "2027-01-01", subject="Bob", predicate="role") == "engineer"
    # and nothing from acme came along
    assert list(target.store.objects(A.tenant, A.namespace)) == []
    target.close()


def test_unscoped_export_requires_admin(two_tenant_engine: Engine) -> None:
    """A principal without 'admin' cannot obtain the whole-store export."""
    with pytest.raises(AuthorizationError):
        two_tenant_engine.export(B, scope="all")
    admin = Principal(tenant="globex", agent="rival", namespace="secret",
                      capabilities=frozenset({"read", "export", "admin"}))
    full = two_tenant_engine.export(admin, scope="all")
    assert {e["tenant"] for e in full["events"]} == {A.tenant, B.tenant}


def test_library_export_without_principal_still_full(two_tenant_engine: Engine) -> None:
    """Anti-regression: the in-process library call keeps whole-store semantics."""
    payload = two_tenant_engine.export()
    assert {e["tenant"] for e in payload["events"]} == {A.tenant, B.tenant}


def test_health_does_not_claim_unverified_integrity(two_tenant_engine: Engine) -> None:
    """A-06: health() must not assert integrity it never checked."""
    eng = two_tenant_engine
    eng.store._conn.execute("UPDATE ledger SET payload_json = ? WHERE seq = 2",
                            ('{"corrupt":true}',))
    default = eng.health()
    assert default.get("integrity_verified") is False
    assert default.get("integrity_ok") is None, (
        "health() claimed integrity_ok without verifying"
    )
    verified = eng.health(verify=True)
    assert verified["integrity_verified"] is True
    assert verified["integrity_ok"] is False
