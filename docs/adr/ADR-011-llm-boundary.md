# ADR-011 — LLM boundary: model-optional core, `NullModelProvider` default

**Status:** Accepted (v0.1)

## Context
The single most consistent census mistake is putting a non-deterministic LLM on the write/CRUD path,
making memory cloud-bound, expensive, non-deterministic, and poisonable.

## Decision
The **core performs no model calls** for any fundamental operation (get, put, retract, timeline,
graph traversal, exact/temporal/metadata query, search-default, export/import). Models reach the
system only through a `ModelProvider` protocol, and the **default is `NullModelProvider`**, whose
enrichment methods (`embed`, `extract_triples`, `summarize`) **raise loudly** so no path can silently
depend on a model. Optional enrichment (entity/relation extraction, summarization, ontology proposal,
entity resolution, query interpretation, embeddings) is exactly that — optional, off the critical
path, and behind the provider.

## Consequences
- The full core runs and is tested with no model and no network (`NULL_LLM_MODE`, zero-egress).
- Ingestion is deterministic and cheap; callers supply structured facts, or opt into an enrichment
  provider they trust.
- Rich auto-extraction from raw text is not a core feature; it is a provider concern.

## Rejected alternatives
- **Mandatory LLM extraction/invalidation** (Graphiti/Cognee/Mem0): rejected (see Context).
- **A "local model" default**: still a dependency + egress risk; `NullModelProvider` is the honest
  zero-dependency default.
