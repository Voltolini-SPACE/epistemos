"""Fixtures for EPISTEMOS-04 Knowledge Spaces tests (SQLite + in-memory, like the core suite)."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.identity import _DEFAULT_CAPS
from epistemos.storage import MemoryStore, SQLiteStore, Store


@pytest.fixture(params=["memory", "sqlite"])
def sengine(request: pytest.FixtureRequest, tmp_path) -> Iterator[Engine]:
    store: Store = MemoryStore() if request.param == "memory" else SQLiteStore(tmp_path / "s.db")
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
