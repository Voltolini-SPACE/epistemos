# ADR-018 — Index consistency: transactional with the projection

**Status:** Accepted (v0.2)

## Context
An index that can silently diverge from the authoritative state produces stale/incomplete results —
the exact failure the mission forbids. v0.1's guarantee is that queryable state is a pure fold over
the ledger; the index must inherit that.

## Decision
The lexical index is updated **inside the same transaction** as the projection: `Engine._persist`
calls `store.put_object` then `index.reindex` on the store's shared SQLite connection, all within one
`store.atomic()`. Therefore an object and its index entry commit or roll back **together** — the
index can never be left inconsistent by a crash (transactional consistency by construction). Live
writes and `rebuild_projection` share `_persist`, so a rebuilt/restored database's index equals a
fresh index over the same events.

Consistency is checkable:

- `verify_index_consistency()` compares the index's `obj_id` set to the authoritative searchable set
  **and** cross-checks `fts_idx`/`fts_map` row counts (detects both mapping drift and content-row
  corruption). On drift it marks the index `DEGRADED`.
- `ensure_built()` runs at open time: a cheap count comparison triggers a one-time rebuild when
  opening a pre-existing or v0.1 (unindexed) database.

## Consequences
- Normal operation keeps the index `HEALTHY` and complete with no extra bookkeeping.
- Opening an old database transparently builds the index once.
- `supersede`/`retract`/`contradict` keep prior versions searchable (historical text search).

## Rejected alternatives
- **Best-effort async index updates**: opens a stale-data window; rejected.
- **A separate index transaction**: cannot be atomic with the projection across a crash; rejected.
