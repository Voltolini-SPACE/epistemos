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
| [015](ADR-015-licensing-strategy.md) | Licensing strategy: Apache-2.0, zero runtime deps, clean-room |
