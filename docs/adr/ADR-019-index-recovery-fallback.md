# ADR-019 — Index recovery & fallback: core never depends on the index

**Status:** Accepted (v0.2)

## Context
The mission's hard rule: *core data must never depend on index integrity*, and a broken index must
never silently return stale/incomplete results.

## Decision
The index is a strictly optional accelerator with **explicit health states** exposed via `health()`:

```
INDEX_HEALTHY      consistent + complete -> safe to use for search
INDEX_DEGRADED     drift/error detected  -> DO NOT use; fall back to scan; rebuildable
INDEX_REBUILDING   rebuild in progress   -> fall back to scan
INDEX_UNAVAILABLE  backend absent (no FTS5, or in-memory backend) -> scan
```

Two guarantees:

1. **Core writes never fail because of the index.** `Engine._persist` isolates *any* exception from
   `index.reindex` (not just SQLite errors), marks the index `DEGRADED`, and lets the authoritative
   write commit. A broken/corrupt index cannot block persistence.
2. **Search never returns stale/incomplete data.** `Engine.search` uses the index **only** when
   `HEALTHY`; on any non-healthy state or a query-time index error it falls back to the correct O(N)
   `LegacyScanRetriever` (which reads live authoritative state) and marks the index degraded. The
   `retrieval_method` field reports which path served the query — the fallback is never hidden.

Recovery is `rebuild_index()` (drop + rebuild from authoritative state), also run automatically once
at open when a count mismatch is detected (`ensure_built`).

## Consequences
- Correctness is preserved under index corruption/deletion/failure (chaos-tested), at the cost of
  slower (scan) search until a rebuild.
- Health is observable, so operators/tests can detect and repair degradation deliberately.

## Rejected alternatives
- **Aborting the core write when indexing fails**: makes core depend on the index; rejected.
- **Serving from a degraded index**: returns silent stale/partial data; rejected.
