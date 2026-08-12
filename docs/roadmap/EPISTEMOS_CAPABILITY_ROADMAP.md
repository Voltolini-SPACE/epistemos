# EPISTEMOS Capability Roadmap (measured, not guessed)

Built from the EPISTEMOS-03 capacity census — every candidate below has a **measured** problem, not
an intuition. `DELIVERED` items shipped in v0.3; the rest carry a decision (`KEEP`/`DEFER`) with the
reason.

## Method

Instrument → measure at 1k/10k/100k → find the real gap → decide by (value × low risk × preserves
invariants). Raw numbers: `docs/benchmarks/EPISTEMOS_03_FINAL_BENCHMARK.md`.

## Candidates and decisions

| # | Candidate | Measured problem | Decision | Notes |
|---|-----------|------------------|----------|-------|
| C2 | **Provenance / explain index** | `explain()` was O(ledger): 14.5 → 158 → **1926 ms** at 1k/10k/100k. | **DELIVERED (v0.3)** | ADR-022. Now flat at ~0.05 ms (33 800× at 100k). Cost: writes ~1.45× slower, DB +18%. |
| C1 | **Unicode-aware search** | Non-ASCII search returned **0 hits** (`Tóquio`, `café`, CJK). | **DELIVERED (v0.3, opt-in)** | ADR-023. SQLite is the single tokenizer authority → scan/index parity by construction. |
| — | **Query-constraint semantics** | Degraded index changed "find what matches" into "list the namespace" (A-03/A-04). | **DELIVERED (v0.3)** | ADR-021. A constraint filters on both paths. |
| C5 | **Ledger snapshot / compaction** | Ledger + DB grow monotonically (~1.9 KB/fact; 100k ≈ 222 MB); `verify_integrity` is O(events) = 2 s at 100k. | **DEFER (EPISTEMOS-06)** | Real, but compaction must preserve tamper-evidence and genealogy — a verifiable snapshot + anchored prune is a design with irreversible consequences. Needs its own ADR + federation context (a compacted export is a knowledge package). |
| C3 | **Hybrid / vector retrieval** | `CANDIDATE_POOL=500` bounds recall for high-frequency terms (500/2000 at 100k). | **DEFER (EPISTEMOS-05)** | ADR-020 designed it; a local, deterministic, no-egress vector backend is buildable but not yet needed by a measured workload. Vector stays OPTIONAL; the core must keep passing with none. |
| C6 | **Bulk ingest** | Write throughput 6 400 facts/s at 100k; no batch API (each fact is its own transaction unless the caller wraps `atomic()`). | **DEFER (EPISTEMOS-05)** | The `atomic()` context already lets a caller batch a load (used by the census). A first-class transactional `ingest_many` is additive; deferred until a real bulk workload justifies the API surface. |
| C9 | **Pagination / streaming** | `search(limit)` caps results; no stable cursor for large sets. | **DEFER (EPISTEMOS-05)** | A tenant-safe, deterministic cursor is additive and low-risk, but no current caller needs >limit results; deferred to avoid a premature API. |
| C8 | **Observability / metrics** | No structured counters (ingest/query/errors/latency/index health). `health()` exposes state but not rates. | **DEFER (EPISTEMOS-04)** | Additive, valuable operationally; must not log content/secrets. Pairs naturally with the capability model (per-capability audit). |
| C7 | **PROV-O / PROV-JSON export** | `explain()` is a bespoke JSON tree; no open-standard provenance export. | **DEFER (EPISTEMOS-06)** | Pairs with federation (a knowledge package's provenance should be a standard). Design only until then. |
| C4 | **Phrase / field-scoped search** | No phrase or per-field (subject/predicate/object) text query. | **DEFER (EPISTEMOS-05)** | FTS5 supports phrase queries; exposing them safely (no injection) is additive on the ADR-023 tokenizer work. |
| — | **Temporal query at scale** | Temporal filter is post-FTS over the candidate pool (fine at 100k: `search` 33 ms). | **KEEP** | No measured problem at target scale; revisit only if a temporal-heavy workload regresses. |
| — | **`verify_integrity` / `health(verify=True)` cost** | O(events): 2 s at 100k; `health(principal)` is O(events) for the scoped count. | **KEEP, note** | Acceptable for an audit operation; if `health` is polled hot at scale, add a cached scoped counter (EPISTEMOS-04 observability). |

## The collaborative direction (owner addendum)

The addendum's vision — private-by-default, shareable-by-permission, collective-by-verification,
federated-by-design — is assessed in `docs/collaboration/`. Its primitives map onto this roadmap:

- **EPISTEMOS-04** — Knowledge Spaces + capability model (turns namespace-as-partition into a real
  authorization boundary; adds observability). *Prerequisite for everything collaborative.*
- **EPISTEMOS-05** — Collaborative claims + evidence + review (claim graph, generational confidence,
  vector/phrase retrieval, bulk ingest, pagination).
- **EPISTEMOS-06** — Knowledge packages + federation (signed exchange, PROV export, compaction).
- **EPISTEMOS-07** — Federated security / reputation / anti-poisoning.

`CAPABILITY_CENSUS = PASS` — roadmap is measurement-driven; the delivered subset (C2, C1, ADR-021)
was chosen for highest measured value at lowest risk while preserving every invariant.
