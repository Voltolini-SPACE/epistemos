# Architecture Decision Records

| ADR | Title |
|-----|-------|
| [001](ADR-001-core-architecture.md) | Core architecture: event-sourced with a rebuildable projection |
| [002](ADR-002-graph-model.md) | Graph model: property graph via typed operations, no query language |
| [003](ADR-003-temporal-model.md) | Temporal model: bitemporal, half-open intervals |
| [004](ADR-004-provenance-model.md) | Provenance model: PROV-aligned genealogy over the ledger |
| [005](ADR-005-memory-taxonomy.md) | Memory taxonomy: semantic types over one store |
| [006](ADR-006-storage-abstraction.md) | Storage abstraction: ports + two independent adapters |
| [007](ADR-007-retrieval-architecture.md) | Retrieval architecture: explainable, deterministic, model-optional |
| [008](ADR-008-identity-tenancy.md) | Identity & tenancy: fail-closed, namespace-as-boundary |
| [009](ADR-009-event-history.md) | Event history: hash-chained, tamper-evident (not "immutable") |
| [010](ADR-010-security-boundary.md) | Security boundary: content is inert data; fail closed |
| [011](ADR-011-llm-boundary.md) | LLM boundary: model-optional core, NullModelProvider default |
| [012](ADR-012-external-apis.md) | External APIs: thin adapters, no implicit authority |
| [013](ADR-013-adapter-architecture.md) | Adapter architecture: CORE ← ADAPTER, never the reverse |
| [014](ADR-014-export-format.md) | Export format: versioned JSON event log, no pickle |
| [015](ADR-015-licensing-strategy.md) | Licensing strategy: Apache-2.0 (superseded by 027), zero runtime deps, clean-room |
| [016](ADR-016-search-index-architecture.md) | Search index architecture: rebuildable projection behind a port (v0.2) |
| [017](ADR-017-fts-implementation.md) | FTS implementation: SQLite FTS5, safe query, parity differences (v0.2) |
| [018](ADR-018-index-consistency.md) | Index consistency: transactional with the projection (v0.2) |
| [019](ADR-019-index-recovery-fallback.md) | Index recovery & fallback: core never depends on the index (v0.2) |
| [020](ADR-020-hybrid-retrieval-scoring.md) | Hybrid retrieval scoring: explicit, optional, no hidden formula (v0.2) |
| [021](ADR-021-query-constraints-filter.md) | A query constraint filters, on both retrieval paths (v0.3) |
| [022](ADR-022-provenance-index.md) | Provenance activity index: explain() stops scanning the ledger (v0.3) |
| [023](ADR-023-unicode-tokenizer.md) | Opt-in unicode search: SQLite is the single tokenizer authority (v0.3) |
| [024](ADR-024-knowledge-spaces.md) | Knowledge Spaces: visibility lattice orthogonal to tenant (v0.4) |
| [025](ADR-025-capability-authorization.md) | Capability-based authorization; roles are capability sets (v0.4) |
| [026](ADR-026-authorized-retrieval.md) | Authorized retrieval: candidate-boundary-first read firewall (v0.4) |
| [027](ADR-027-mit-license.md) | Relicense to MIT (v0.4) |
| [028](ADR-028-collaborative-claims.md) | Collaborative claims: a claim graph distinct from the knowledge graph (v0.5) |
| [029](ADR-029-derived-belief-governed-acceptance.md) | Belief is derived; acceptance is governed via a policy port (v0.5) |
| [030](ADR-030-panel-architecture.md) | Panel architecture: the UI is a consumer, authority stays in the core (panel-v1) |
| [031](ADR-031-event-boundary-sse.md) | Real-time event boundary: Server-Sent Events over the ledger (panel-v1) |
| [032](ADR-032-authorized-read-model-and-stream.md) | Authorized read-model & server-side stream filtering (panel-v1) |
