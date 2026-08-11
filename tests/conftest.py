"""Shared fixtures. The `engine` fixture is parametrized over BOTH storage adapters so
every functional test doubles as a store-conformance test with no test-side branching."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from epistemos import Engine, Principal
from epistemos.storage import MemoryStore, SQLiteStore, Store


class ManualClock:
    """Deterministic clock: strictly increasing UTC, +1s per call. Base is after the
    fixture dates used in temporal tests so 'now' sits in their future."""

    def __init__(self, start: datetime | None = None) -> None:
        self.t = start or datetime(2026, 6, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        v = self.t
        self.t = self.t + timedelta(seconds=1)
        return v


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path) -> Iterator[Store]:
    if request.param == "memory":
        s: Store = MemoryStore()
    else:
        s = SQLiteStore(tmp_path / "k.db")
    yield s
    s.close()


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def engine(store: Store, clock: ManualClock) -> Engine:
    return Engine(store, clock=clock)


@pytest.fixture
def ctx() -> Principal:
    return Principal(tenant="acme", agent="claude", namespace="hr")
