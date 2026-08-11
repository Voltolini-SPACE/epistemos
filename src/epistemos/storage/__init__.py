"""Storage ports and adapters. The domain depends on :class:`Store` only."""

from __future__ import annotations

from pathlib import Path

from .memory import MemoryStore
from .ports import Store
from .sqlite import SQLiteStore

__all__ = ["Store", "MemoryStore", "SQLiteStore", "open_store"]


def open_store(target: str | Path | None) -> Store:
    """Open a store. ``None`` or ``":memory:"`` -> in-memory; a path -> SQLite file."""
    if target is None or target == ":memory:":
        return MemoryStore()
    return SQLiteStore(target)
