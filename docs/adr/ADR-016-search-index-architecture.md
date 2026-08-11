# ADR-016 — Search index architecture: a rebuildable projection behind a port

**Status:** Accepted (v0.2, EPISTEMOS-02)

## Context
v0.1 measured a real O(N) retrieval bottleneck: text search scans and scores every scoped object
(116 ms/1k → 722 ms/10k → 7.4 s/100k). The `docs/benchmarks/RETRIEVAL_PROFILE_BASELINE.md` profile
confirms the cost is per-candidate work (scan + tokenize + score + temporal + serialize) that scales
with the corpus, not the result set.

## Decision
Introduce a **substitutable index layer** (`epistemos/index/`) with a `LexicalIndex` port (plus
design-only `VectorIndex`/`HybridScoring` boundaries). The index is a **rebuildable projection of the
authoritative state (ledger + primary store), never a source of truth**. The retriever gets a small
candidate set from the index (O(matches)) and runs the **existing explainable scorer** over it, so
temporal/authority/exact/recency components and `why_returned` are unchanged. Text search uses the
index only when it is `HEALTHY`; otherwise it falls back to the correct O(N) scan (ADR-019).

## Consequences
- Search drops from O(corpus) to O(matches) for text queries; all v0.1 semantics preserved.
- The index can be dropped and rebuilt from authoritative state at any time.
- Structural (subject/predicate) and no-text queries keep using fast indexed columns (unchanged).

## Rejected alternatives
- **Replace the domain scorer with the backend's opaque score**: forfeits explainability; rejected —
  the backend supplies only the lexical candidate/score; the domain still ranks (ADR-017).
- **Make the index a source of truth**: violates the event-sourcing invariant; rejected.
- **A distributed search service**: no measured need; violates local-first/zero-egress (mission §39).
