"""SCHEMA_MIGRATION gate (checkpoint Q).

A v0 fixture is migrated forward to the current schema and re-sealed on import; data is
preserved. Forward-incompatible and downgrade cases fail closed.
"""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal
from epistemos.errors import SchemaError
from epistemos.schema import CURRENT_SCHEMA, migrate_export
from epistemos.storage import MemoryStore


def _v0_export() -> dict:
    """A hand-built v0-shaped export: fact uses valid_start, no status/schema_version."""
    return {
        "format": "epistemos-events",
        "schema_version": 0,
        "events": [
            {
                "op": "source_added", "ts": "2026-01-01T00:00:00Z", "tenant": "t",
                "namespace": "n", "actor": "a", "principal": None,
                "payload": {
                    "id": "src_1", "kind": "source", "tenant": "t", "namespace": "n",
                    "owner": "a", "created_at": "2026-01-01T00:00:00Z", "uri": "mem://s",
                    "source_kind": "note", "trust": 0.7, "confidence": 1.0, "metadata": {},
                },
            },
            {
                "op": "fact_asserted", "ts": "2026-01-02T00:00:00Z", "tenant": "t",
                "namespace": "n", "actor": "a", "principal": None,
                "payload": {
                    "id": "fact_1", "kind": "fact", "tenant": "t", "namespace": "n",
                    "owner": "a", "created_at": "2026-01-02T00:00:00Z", "subject": "Alice",
                    "predicate": "works_at", "object": "Acme", "valid_start": "2026-01-01",
                    "tx_from": "2026-01-02T00:00:00Z", "tx_to": None, "confidence": 1.0,
                    "memory_class": "semantic", "metadata": {}, "source": "src_1",
                },
            },
        ],
    }


def test_migrate_transforms_shape() -> None:
    migrated = migrate_export(_v0_export())
    assert migrated["schema_version"] == CURRENT_SCHEMA
    fact = migrated["events"][1]["payload"]
    assert "valid_start" not in fact
    assert fact["valid_from"] == "2026-01-01"
    assert fact["status"] == "asserted"


def test_migrated_import_preserves_data() -> None:
    ctx = Principal(tenant="t", agent="a", namespace="n")
    eng = Engine(MemoryStore())
    n = eng.import_events(_v0_export(), migrate=True)
    assert n == 2
    assert eng.current(ctx, subject="Alice", predicate="works_at") == "Acme"
    assert eng.verify_integrity() == 2  # re-sealed chain is valid


def test_import_old_without_migrate_flag_fails_closed() -> None:
    eng = Engine(MemoryStore())
    with pytest.raises(SchemaError):
        eng.import_events(_v0_export())  # migrate=False


def test_forward_incompatible_rejected() -> None:
    future = {"format": "epistemos-events", "schema_version": 999, "events": []}
    with pytest.raises(SchemaError, match="forward-incompatible"):
        migrate_export(future)
