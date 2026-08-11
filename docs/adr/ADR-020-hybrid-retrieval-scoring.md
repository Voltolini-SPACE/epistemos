# ADR-020 — Hybrid retrieval scoring: explicit, optional, no hidden formula

**Status:** Accepted (v0.2) — design foundation; vector/graph components not implemented in v0.2

## Context
Future retrieval will combine lexical, vector, graph, temporal, authority and recency signals. The
mission requires this to be designed now (not forced to implement) with **explicit** scoring — no
arbitrary hidden formula — and vector search must stay **optional** (core passes with no embeddings).

## Decision
A future `HybridRetriever` combines independent, normalized-`[0,1]` components as a **transparent
weighted sum**, extending today's lexical retriever rather than replacing it:

```
total = w_lexical*lexical + w_vector*vector + w_graph*graph
      + w_exact*exact + w_temporal*temporal + w_authority*authority + w_recency*recency
```

- Every component and weight is reported in `score_components`; `why_returned` explains the mix.
- **Vector and graph are optional.** With their backends absent they contribute 0 and the
  lexical+temporal+authority+exact+recency core is unchanged. The `VectorIndex` port exists
  (`index/__init__.py`) with `NullVectorIndex` as the default — **no model, no download, no egress**
  (`VECTOR_OPTIONAL`). `HybridScoring` (design anchor) names the components and the combination rule.
- Ranking never collapses distinct dimensions into one opaque number: trust ≠ confidence ≠ lexical.

## Consequences
- v0.2 ships the lexical/temporal/authority/exact/recency subset (fully implemented + explainable).
- Adding vector/graph later is additive and cannot silently change existing behavior (absent = 0).
- The scoring contract stays inspectable and testable.

## Rejected alternatives
- **A learned/opaque ranker**: not explainable; rejected for the core (could be an optional reranker
  behind a port later).
- **Mandating vector search**: breaks zero-egress/model-agnostic; rejected — it stays optional.
