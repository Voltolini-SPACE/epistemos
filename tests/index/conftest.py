"""Fixtures for the FTS index tests. These target the SQLite backend, where the index is
active (the in-memory backend intentionally keeps the O(N) scan)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.storage import SQLiteStore


@pytest.fixture
def fts(tmp_path) -> Iterator[Engine]:
    eng = Engine(SQLiteStore(tmp_path / "idx.db"), clock=ManualClock())
    yield eng
    eng.close()


@pytest.fixture
def ctx() -> Principal:
    return Principal(tenant="acme", agent="claude", namespace="hr")
