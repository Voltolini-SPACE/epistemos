# ADR-007 — Retrieval architecture: explainable, deterministic, model-optional

**Status:** Accepted (v0.1)

## Context
Retrieval must be explainable (mission §15) and must work with no model (`NULL_LLM_MODE`). Opaque
vector similarity (Mem0/Letta) forfeits trust; the census favors hybrid, inspectable retrieval.

## Decision
Retrieval is a **transparent weighted combination of independent scorers** — `lexical` (TF·IDF),
`exact` (structural s/p/o match), `recency` (transaction time), `authority` (source trust),
`temporal` (currently believed & valid) — combined by configurable `Weights`. Every result carries
`score`, `score_components`, `retrieval_method`, `source`, `temporal_state`, and a human `why_returned`.
The default path uses **no model** (deterministic). A **`VectorStore`/embedding path is an optional,
pluggable port**: absent (NullModelProvider) it simply contributes no component — there is no opaque
"vector" score by default.

## Consequences
- Explainable retrieval works under `NullModelProvider` (tested).
- Source **trust** and fact **confidence** are distinct components, never merged.
- **Measured limitation:** the lexical scorer is a full scan → search is O(N) (benchmark: 116ms@1k,
  722ms@10k, 7.4s@100k). This is the designated seam for an FTS/ANN index (a `candidates()` port
  method) if a measured workload needs 100k-scale search. v0.1 targets local small/medium bases.

## Rejected alternatives
- **Embedding-only retrieval**: opaque, model-required; rejected.
- **Building the FTS/ANN index now**: no measured need at v0.1 target scale; deferred per mission §39,
  with the port designed to accept it.
