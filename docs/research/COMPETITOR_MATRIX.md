# Competitor Forensic Matrix

Census date **2026-08-11**. Cells are **MEASURED** from repos/licenses/docs unless marked
**CLAIM** (marketing, unverified). Do not read a CLAIM as a fact (mission §6).

## Identity

| System | Repo / org | License | Lang | Primary architecture |
|--------|-----------|---------|------|----------------------|
| **Semantica** | semantica-agi/semantica | MIT | Python | deterministic ingest pipeline → polyglot RDF+LPG+vector |
| **Graphiti / Zep** | getzep/graphiti | Apache-2.0 | Python | LLM-built temporal KG over Neo4j/FalkorDB |
| **MS GraphRAG** | microsoft/graphrag | MIT | Python | batch LLM index + community summaries |
| **Cognee** | topoteretes/cognee | Apache-2.0 | Python | ECL pipeline, embedded SQLite+LanceDB+graph |
| **Mem0** | mem0ai/mem0 | Apache-2.0 | Python | LLM add/search/update memory layer |
| **Letta/MemGPT** | letta-ai/letta | Apache-2.0 | Python | stateful agent OS, memory-as-tools |
| **TrustGraph** | trustgraph-ai/trustgraph | Apache-2.0 | Python | PROV-O KG over broker+Cassandra+Qdrant |
| **ABI / Naas** | jupyter-naas/abi | MIT | Python | BFO-typed graph, hexagonal ports |
| **EPISTEMOS** | (this repo) | Apache-2.0 | Python (stdlib-only) | event-sourced bitemporal core + ports |

## Capability comparison

| System | Bitemporal (valid+tx) | Provenance | LLM required (write) | Local-first / zero-egress | Tenant isolation | Explainable retrieval | Decisions first-class | Tamper-evident |
|--------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Semantica | CLAIM | PROV-O ✔ | optional | embedded option | ? | ✔ (subgraph) | ✔ | ✖ |
| Graphiti/Zep | ✔ (edge) | episode-level | **yes** | ✖ (cloud default) | soft (group_id) | partial | ✖ | ✖ |
| MS GraphRAG | ✖ | chunk-id | **yes** | ✔ files / cloud LLM | ✖ | ✔ (context records) | ✖ | ✖ |
| Cognee | ✖ (bolt-on) | doc-level | **yes** | ✔ embedded | opt-in | ✔ (typed enum) | ✖ | ✖ |
| Mem0 | ✖ (tx only) | severed | **yes** | possible (local) | scope field | ✖ (embedding) | ✖ | ✖ |
| Letta | ✖ (tx only) | none/summary | **yes** | possible | block/agent | ✖ | ✖ | ✖ |
| TrustGraph | ✖ | **PROV-O ✔** | **yes** | local option | ? | **✔ (DAG)** | ✖ | ✖ |
| ABI | ✖ (reified) | compliance | **yes** | ✔ no-docker | ? | ✔ (SPARQL) | ✖ | ✖ |
| **EPISTEMOS** | **✔ tested** | **✔ hashed + PROV-style** | **no** | **✔ measured** | **✔ fail-closed** | **✔ (score components)** | **✔** | **✔ (hash chain)** |

## Reading of the matrix

- **Bitemporality** is the rare, decisive primitive: only Graphiti has it as a genuine, verified
  core model; Semantica *claims* it (unverified); everyone else is transaction-time-only or bolts it on.
- **Every LLM-native memory system** (Graphiti, GraphRAG, Cognee, Mem0, Letta, TrustGraph) puts the
  model on the **write path**, making memory non-deterministic, cloud-coupled, and poisonable. This is
  the single most consistent architectural mistake in the field.
- **Provenance** ranges from none (Mem0/Letta) to strong-and-standardized (TrustGraph PROV-O), but
  **no surveyed system content-hashes its provenance** into a tamper-evident structure.
- **Tenant isolation** is universally weak (a filter/scope field or opt-in), never fail-closed.

EPISTEMOS is positioned to be the only surveyed design that is **simultaneously** bitemporal,
deterministic (no-LLM core), hash-anchored-provenance, fail-closed multi-tenant, explainable, and
local-first zero-egress — see [`FEATURE_HARVEST.md`](FEATURE_HARVEST.md) and
[`EPISTEMOS_RESEARCH_FINAL.md`](EPISTEMOS_RESEARCH_FINAL.md).
