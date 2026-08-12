"""SCHEMA_MIGRATION gate (checkpoint Q).

A v0 fixture is migrated forward to the current schema and re-sealed on import; data is
preserved. Forward-incompatible and downgrade cases fail closed.
"""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal
from epistemos._util import canonical_json, sha256_hex
from epistemos.errors import IntegrityError, SchemaError
from epistemos.ledger import GENESIS_HASH, content_hash
from epistemos.schema import CURRENT_SCHEMA, migrate_export
from epistemos.storage import MemoryStore


def _seal_v0(payload: dict) -> dict:
    """Seal a v0-shaped export over its ORIGINAL payloads.

    An old export is only importable if it is tamper-evident on its own terms: migration
    reshapes payloads (invalidating the original content hashes), so the chain must be
    verified as received, before migrating (EPISTEMOS-03, A-02).
    """
    prev = GENESIS_HASH
    for seq, ev in enumerate(payload["events"], start=1):
        ch = content_hash(ev["op"], ev["payload"])
        header = {
            "seq": seq, "ts": ev["ts"], "op": ev["op"], "tenant": ev["tenant"],
            "namespace": ev["namespace"], "actor": ev["actor"],
            "principal": ev["principal"], "content_hash": ch, "prev_hash": prev,
        }
        entry = sha256_hex(canonical_json(header))
        ev.update(seq=seq, content_hash=ch, prev_hash=prev, entry_hash=entry)
        prev = entry
    return payload


def _v0_export(*, sealed: bool = True) -> dict:
    """A hand-built v0-shaped export: fact uses valid_start, no status/schema_version."""
    payload = {
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
    return _seal_v0(payload) if sealed else payload


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


def test_migrate_rejects_tampered_old_export() -> None:
    """A-02: migrate=True must verify the chain it was handed, not just re-seal it."""
    payload = _v0_export()
    payload["events"][1]["payload"]["object"] = "TAMPERED"
    eng = Engine(MemoryStore())
    with pytest.raises(IntegrityError):
        eng.import_events(payload, migrate=True)
    ctx = Principal(tenant="t", agent="a", namespace="n")
    assert eng.current(ctx, subject="Alice", predicate="works_at") is None


def test_chainless_export_refused_unless_explicitly_unverified() -> None:
    """An export with no hash chain is unverifiable — never silently treated as verified."""
    eng = Engine(MemoryStore())
    with pytest.raises(IntegrityError, match="no verifiable hash chain"):
        eng.import_events(_v0_export(sealed=False), migrate=True)
    # the caller may still opt in explicitly, and it is then plainly unverified
    lenient = Engine(MemoryStore())
    assert lenient.import_events(_v0_export(sealed=False), migrate=True, verify=False) == 2
