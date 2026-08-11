# ADR-006 — Storage abstraction: ports + two independent adapters

**Status:** Accepted (v0.1)

## Context
The domain must not depend conceptually on any specific backend (mission §17). We also need
crash-consistency and a way to prove the abstraction is real, not decorative.

## Decision
An abstract `Store` port defines the persistence + structural-index surface (atomic transactions,
append/head/read_events, object CRUD, fact/relation indexes, counts, clear_projection). The domain
depends only on `Store`. Two **independent** adapters implement it: `MemoryStore` (pure Python,
canonical-JSON) and `SQLiteStore` (single file, WAL, `synchronous=FULL`). Event-sealing math is
shared in the port so both chain identically. One conformance suite (the parametrized `engine`
fixture + `test_store_conformance`) runs against both with no test-side branching, proving identical
semantics.

## Consequences
- Storage-agnosticism is demonstrated, not claimed (two adapters, one suite).
- `MemoryStore` gives fast tests; `SQLiteStore` gives durable local persistence.
- Query methods filter strictly by `(tenant, namespace)` — defense-in-depth for isolation.

## Rejected alternatives
- **A single SQLite-only implementation** with a thin wrapper: does not prove abstraction; rejected.
- **Neo4j/pgvector/etc. in the core**: infra coupling + egress; kept as *future* adapters behind the
  same port (ADR-013), never a core dependency.
