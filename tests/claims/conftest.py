"""Fixtures for EPISTEMOS-05 Collaborative Claims tests (SQLite + in-memory parity)."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.identity import _DEFAULT_CAPS
from epistemos.storage import MemoryStore, SQLiteStore, Store

# a curator holds the governed truth gate (knowledge.accept) on top of the default rights
CURATOR_CAPS = _DEFAULT_CAPS | {"knowledge.accept", "knowledge.promote"}


@pytest.fixture(params=["memory", "sqlite"])
def cengine(request: pytest.FixtureRequest, tmp_path) -> Iterator[Engine]:
    store: Store = MemoryStore() if request.param == "memory" else SQLiteStore(tmp_path / "c.db")
    eng = Engine(store, clock=ManualClock())
    yield eng
    eng.close()


def principal(agent: str, *, tenant: str = "acme", namespace: str = "hr",
              extra_caps: frozenset[str] = frozenset()) -> Principal:
    return Principal(tenant=tenant, agent=agent, namespace=namespace,
                     capabilities=_DEFAULT_CAPS | extra_caps)


@pytest.fixture
def alice() -> Principal:
    return principal("alice")


@pytest.fixture
def bob() -> Principal:
    return principal("bob")


@pytest.fixture
def carol() -> Principal:
    return principal("carol")


@pytest.fixture
def curator() -> Principal:
    return principal("curator", extra_caps=frozenset({"knowledge.accept", "knowledge.promote"}))
