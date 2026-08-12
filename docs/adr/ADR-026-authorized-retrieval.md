# ADR-026 — Authorized retrieval: the read firewall is candidate-boundary-first

**Status:** Accepted (v0.4)

## Context

Mission §12 forbids the architecture *global search → rank → filter permissions*, because an
unauthorized object's score, timing, count or metadata could leak its existence. Authorization must
precede retrieval: *authorized-space-set → candidate boundary → retrieval → ranking → explain*.
This is the P0 (`PRIVATE_TO_PUBLIC_LEAK = 0`).

## Decision

**Every read surface applies the space firewall to candidates *before* any scoring, ranking or
listing.** One predicate, `Engine._can_read` (delegating to the pure `authz.can_read_object`), is
threaded through all of them:

| Surface | How the firewall is applied |
|---|---|
| `get` | returns `None` for an unreadable object (no existence oracle across the space edge) |
| `search` (both retrievers) | an `authorize` predicate drops unauthorized candidates **before** TF·IDF/BM25 scoring, so they never affect df/idf, score, rank or count |
| `current` / `as_of` / `facts_for` / `timeline` | facts filtered by `_readable` before `resolve_current`/ordering |
| `recall` | filtered while listing (meta objects excluded) |
| `explain` (provenance) | genealogy nodes the caller cannot read are **elided** (`status=out_of_scope`) — a private ancestor of a shared object never leaks its content |
| `neighbors` / `query_graph` (graph) | an edge is returned only if the relation **and its far endpoint** are readable, so a private node's existence cannot be inferred through a readable one (§19) |
| `export(principal)` | the scoped slice contains only events for objects the caller may currently read (§18) |

The scan fallback enforces the **same** predicate as the FTS path (a degraded index never leaks —
`test_degraded_index_fallback_does_not_leak`, mutant `spaces_search_authorize_removed`).

The index remains a **rebuildable projection, never a source of truth**: the FTS query still scopes
`(tenant, namespace)` at the SQL boundary; the space predicate is applied over the returned
candidates before ranking. A corrupted index falls back to the scan without leaking.

## Consequences

- **No score/rank/count/timing leak from ranking:** because unauthorized candidates are removed
  before the corpus is scored, another agent's query behaves as if the private objects do not exist
  (`test_search_score_and_count_do_not_leak`).
- **Cost (measured, §31):** for a private single-agent corpus the firewall adds a cheap per-candidate
  owner check — common-term search ≈1.6× at 100k, rare-term/`current`/`as_of`/`get` unchanged. For a
  tenant-wide (ORG) corpus a space lookup per candidate applies. Security is not traded for speed.
- **Residual (documented, deferred):** the FTS MATCH still resolves over the whole namespace before
  the space predicate, so search *latency* couples across spaces within a namespace (the OV-04
  coupling, one level up). Per-space index **partitioning** — making the candidate boundary the
  authorized-space set *in SQL* — is a follow-up; it removes the timing side-channel entirely. It is
  not required for `CROSS_SPACE_RETRIEVAL_LEAK=0` (no content/score/count leak exists), only for
  timing isolation.

## Rejected alternatives

- **Filter after ranking** — rejected (mission §12: leaks score/rank/count/timing).
- **Push per-principal space membership into the FTS SQL** — deferred: membership is dynamic
  projected state, not a static column; the candidate-first Python filter is correct today and the
  SQL partitioning is the performance follow-up, not a correctness gap.
