"""Schema versioning & migration (mission §36, gate SCHEMA_MIGRATION).

``schema_version`` exists from v0.1 (not deferred). Migrations operate on an **export
payload** (portable JSON), transforming old-shape data forward to the current schema.

Migrating a hash-chained ledger necessarily changes payloads, which changes content
hashes — so an imported *migrated* export is **re-sealed** into a fresh chain (see
``Engine.import_events(..., migrate=True)``). Same-version import stays verbatim and
preserves the original tamper-evident hashes. Downgrades are intentionally unsupported.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import SchemaError
from .model import SCHEMA_VERSION

__all__ = ["CURRENT_SCHEMA", "migrate_export", "MIGRATIONS"]

CURRENT_SCHEMA = SCHEMA_VERSION


def _v0_to_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a hypothetical v0 export to v1.

    v0 shape assumptions (as shipped by an imagined 0.0.x): fact payloads used
    ``valid_start``/``valid_end`` and had no ``status``/``schema_version``. v1 renames
    those to ``valid_from``/``valid_to`` and derives ``status`` from the belief interval.
    """
    events = []
    for ev in payload.get("events", []):
        ev = dict(ev)
        p = dict(ev.get("payload", {}))
        if p.get("kind") == "fact":
            if "valid_start" in p:
                p["valid_from"] = p.pop("valid_start")
            if "valid_end" in p:
                p["valid_to"] = p.pop("valid_end")
            p.setdefault("valid_from", None)
            p.setdefault("valid_to", None)
            if "status" not in p:
                p["status"] = "asserted" if p.get("tx_to") is None else "superseded"
            p["schema_version"] = 1
        ev["payload"] = p
        events.append(ev)
    out = dict(payload)
    out["events"] = events
    out["schema_version"] = 1
    return out


# from-version -> function upgrading the payload by exactly one major version
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    0: _v0_to_v1,
}


def migrate_export(payload: dict[str, Any]) -> dict[str, Any]:
    """Return ``payload`` upgraded to :data:`CURRENT_SCHEMA`. Fail closed on gaps/downgrades."""
    if not isinstance(payload, dict):
        raise SchemaError("export payload must be a mapping")
    version = int(payload.get("schema_version", 0))
    if version == CURRENT_SCHEMA:
        return payload
    if version > CURRENT_SCHEMA:
        raise SchemaError(
            f"forward-incompatible export (schema {version} > engine {CURRENT_SCHEMA}); "
            "downgrade is unsupported"
        )
    while version < CURRENT_SCHEMA:
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise SchemaError(f"no migration registered from schema version {version}")
        payload = migration(payload)
        version = int(payload.get("schema_version", version + 1))
    return payload
