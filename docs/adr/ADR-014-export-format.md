# ADR-014 — Export format: versioned JSON event log, no pickle

**Status:** Accepted (v0.1)

## Context
EPISTEMOS must not become a data prison (mission §35): data must be exportable in a documented,
versioned, safe format, and re-importable with integrity.

## Decision
Export is the **full, versioned event ledger as JSON**:
`{format: "epistemos-events", schema_version, exported_at, event_count, events: [...]}` where each
event includes its `content_hash`/`prev_hash`/`entry_hash`. **No pickle** — JSON only (safe
deserialization). Import into an **empty** store is **verbatim and verified** (`verify_chain`),
preserving original tamper-evident hashes; a single-byte tamper is detected. Migrated import
(`migrate=True`) upgrades an older-schema export via `schema.migrate_export` and **re-seals** into a
fresh chain (payloads change shape, so original hashes cannot be preserved — a documented
consequence). Import into a non-empty store is refused (`ConflictError`). PROV-O/PROV-JSON is a
planned additional export view (does not replace the ledger export).

## Consequences
- Full-fidelity portability + tamper detection on import.
- Round-trip logical equivalence across backends (tested).
- The export is the backup/restore substrate too (ADR-relates to backup).

## Rejected alternatives
- **Pickle / arbitrary object serialization**: deserialization attack surface; rejected.
- **Exporting only current state (no history)**: loses provenance/temporal; rejected.
- **Migrating in place over the original chain**: breaks hashes silently; re-seal is explicit instead.
