# ADR-001 — Core architecture: event-sourced with a rebuildable projection

**Status:** Accepted (v0.1)

## Context
EPISTEMOS must be provenance-first, tamper-evident, crash-consistent, and able to reconstruct past
belief. The census showed most systems mutate current state in place and treat history as a log
side-effect, which defeats point-in-time reconstruction and audit.

## Decision
The **append-only, hash-chained event ledger is the source of truth**. All queryable state
(entities, facts, relations, decisions) is a **materialized projection** produced by a single
`_apply(record)` function. Live writes and import/restore share `_apply`, so state is a pure fold
over the ledger and is fully rebuildable (`rebuild_projection`). Every mutation follows exactly one
path: `command → validation → auth/tenant → event → ledger → projection → result` — there is no code
that writes projection state without first appending an event (`test_no_direct_mutation`).

## Consequences
- Crash consistency and rollback are structural (one transaction wraps append + projection).
- Backup/restore, export/import, and crash recovery all reduce to replaying the ledger.
- Slightly more write work than in-place mutation; acceptable (write p50 ~0.4ms, benchmark).

## Rejected alternatives
- **Mutate-in-place current state** (Mem0/Letta): loses history and reconstruction; rejected.
- **Separate audit log alongside a mutable DB**: two sources of truth drift; rejected.
