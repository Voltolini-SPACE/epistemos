"""PYTHON_SDK gate (checkpoint X) — LocalClient. (RemoteClient is covered in test_rest.)

The SDK duplicates no domain rules: LocalClient delegates straight to the Engine and shares
its error semantics.
"""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal
from epistemos.errors import NotFoundError, ValidationError
from epistemos.sdk import LocalClient
from epistemos.storage import MemoryStore

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> LocalClient:
    engine = Engine(MemoryStore())
    return LocalClient(engine, Principal(tenant="acme", agent="sdk", namespace="default"))


def test_local_client_full_flow(client: LocalClient) -> None:
    sid = client.add_source(uri="mem://s", trust=0.7)
    fid = client.assert_fact(subject="Alice", predicate="works_at", object="Acme", source=sid)
    assert client.current(subject="Alice", predicate="works_at") == "Acme"
    assert client.timeline(subject="Alice")
    assert client.explain(fid)["id"] == fid
    assert client.health()["event_count"] >= 2
    assert client.export()["format"] == "epistemos-events"


def test_local_client_shares_error_semantics(client: LocalClient) -> None:
    with pytest.raises(ValidationError):
        client.assert_fact(subject="A", predicate="p", object="B", valid_from="bad")
    with pytest.raises(NotFoundError):
        client.explain("fact_missing")


def test_local_client_scoped_to_principal(client: LocalClient) -> None:
    client.assert_fact(subject="Secret", predicate="p", object="V")
    other = LocalClient(client._engine, Principal(tenant="other", agent="x", namespace="default"))
    assert other.current(subject="Secret", predicate="p") is None
