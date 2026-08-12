# ADR-022 — Provenance activity index: explain() stops scanning the ledger

**Status:** Accepted (v0.3)

## Context

`explain(id)` answers *where did this come from and what happened to it*. Its activity list is
built by `provenance._activities_for`, which in v0.2 read **every ledger event** and tested each
payload for a reference to the id — once per node of the genealogy tree. The reverse
`superseded_by` edge separately scanned **every fact** in the namespace, also per node.

So the cost of explaining one fact was a function of the size of the entire history, not of that
fact's genealogy. Measured on the frozen v0.2.0 tag (`tools`-free harness, 10-core M-series,
Python 3.14.5):

| ledger events | `explain()` p50 |
|---|---|
| 1 000 | 14.5 ms |
| 10 000 | 158.1 ms |
| 100 000 | **1 926.4 ms** |

Linear, and already unusable at a scale the FTS work (v0.2) made routine: a store that answers
text search in 32 ms took nearly two seconds to explain a single fact. Provenance is the
product's core promise; it should not be the slowest operation in it.

## Decision

Add `index/provenance.py::SqliteProvenanceIndex`, a rebuildable projection `obj_id -> [seq, …]`,
following the `index/fts.py` contract exactly (ADR-016/018/019):

- **Same database, same connection, same transaction** as the store, so an index write commits or
  rolls back with the authoritative write and cannot silently diverge on a crash.
- **A projection, never a source of truth.** It is rebuilt from the ledger by `rebuild_index()` and
  `rebuild_projection()`, and every question it answers must be answerable without it.
- **Health-gated with a scan fallback.** `IndexHealth` is reported through `health()`; anything
  other than `HEALTHY` (or any error mid-query) falls back to the authoritative scan. The
  fallback returns the *same rows in the same order* — the gate is equality, not similarity.
- **Only id-shaped leaves are indexed** (`prefix_<32 hex>`, the shape `_util.new_id` mints). The
  scan it replaces matches an id wherever it appears as a string value, so indexing that shape is
  exact for any id the engine minted. `is_indexable()` gates every lookup, so an object with a
  hand-authored id — from an imported export, say — is served by the scan instead. Correct, just
  not accelerated.

`Store.records_by_seq` is added to the port with a correct O(events) default, overridden by
`SQLiteStore` with a keyed `WHERE seq IN (…)`. Adapters that do not override it keep working.

## Consequences

Measured before (v0.2.0) vs after, same harness and machine:

| metric | scale | before | after | delta |
|---|---|---|---|---|
| `explain()` p50 | 1 000 | 14.5 ms | 0.064 ms | **226× faster** |
| `explain()` p50 | 10 000 | 158.1 ms | 0.052 ms | **3 022× faster** |
| `explain()` p50 | 100 000 | 1 926.4 ms | 0.053 ms | **36 278× faster** |
| write throughput | 100 000 | 9 337/s | 6 738/s | 1.39× slower |
| `rebuild_projection` | 100 000 | 4.45 s | 6.46 s | 1.45× slower |
| `rebuild_index` | 100 000 | 1.84 s | 3.91 s | 2.1× slower (two indexes now) |
| database size | 100 000 | 187.9 MB | 222.9 MB | +18.6% |
| `search`, `current`, `as_of`, `verify_integrity` | all | — | — | unchanged |

`explain()` becomes flat in ledger size — it is now proportional to the genealogy actually walked.
The costs are real and disclosed: roughly 1.2–1.4× on writes, ~19% on disk, and a second index to
rebuild. For an engine whose stated purpose is answering provenance questions, that is the right
side of the trade.

**Implementation note kept deliberately visible.** The first working version made
`rebuild_projection` at 100k take **270 s** instead of 4.45 s — a 60× regression. `record()`
issues an idempotency `DELETE … WHERE seq = ?`, and `prov_ref`'s primary key is `(obj_id, seq)`,
so that delete had no usable index and degraded the rebuild to O(events²). Adding
`idx_prov_ref_seq` brought it to 6.46 s. The lesson is recorded here because the benchmark, not
the test suite, is what caught it: all 655 tests passed at 270 s.

## Rejected alternatives

- **Index every string leaf, not just id-shaped ones.** Removes the `is_indexable` gate and the
  need for a fallback on odd ids, but multiplies index rows by roughly 5× (every subject,
  predicate, object, timestamp) to accelerate a case that does not occur for engine-minted data.
- **Materialize the explanation itself** (cache the `explain()` result per object). Rejected: the
  answer depends on depth and on later events, so the cache would need invalidating on every
  write — and a stale *explanation* is far more dangerous than a stale search hit.
- **Store the reverse edges on the object** (`superseded_by` as a field). Rejected: it makes the
  projection carry derived data that the ledger already determines, and a wrong value there is
  indistinguishable from truth. The index can always be dropped and rebuilt; a field cannot.
- **A separate index database.** Rejected for the same reason as ADR-018: it loses transactional
  consistency with the store.
