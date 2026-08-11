# ADR-005 — Memory taxonomy: semantic types over one store

**Status:** Accepted (v0.1)

## Context
"Memory" must not collapse to embeddings (mission §12). We need working / episodic / semantic /
procedural / long-term / session memory, but not four arbitrary databases.

## Decision
Memory classes are **semantic types**, not separate stores: a `memory_class` label on facts plus
first-class `Episode`/`Observation` objects, all in the one ledger-backed store. A machine-readable
`MemorySpec` table (`memory/`) defines each class's scope, retention, mutability, temporal
applicability, and provenance requirement, and tests assert the distinctions are real (e.g. working
is mutable/non-temporal/provenance-optional; semantic/episodic/procedural/long-term are
append-only/temporal/provenance-required). `recall(memory_class=…, session=…)` queries by class.

## Consequences
- One consistency boundary, one backup, one integrity chain across all memory classes.
- Class semantics are enforceable and documented (`docs/spec/MEMORY_MODEL.md`).
- Working/session ephemerality is a policy the caller enforces (no auto-eviction daemon in v0.1).

## Rejected alternatives
- **Four separate databases** (one per memory type): sync/consistency burden; no cross-class
  provenance; rejected as over-engineering (mission §39).
- **Memory = embeddings only** (Mem0/Letta retrieval): opaque, un-typed; rejected.
