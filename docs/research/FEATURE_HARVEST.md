# Feature Harvest

For each harvested property: **SOURCE_CONCEPT** → decision (**KEEP / MODIFY / REJECT**) →
**EPISTEMOS_DESIGN** (with the module that implements it). Mission §7.

| # | Source concept (from) | Why good | Why bad / risk | Decision | EPISTEMOS design |
|---|----------------------|----------|----------------|----------|------------------|
| 1 | **Bitemporal edge** — valid + tx time (Graphiti; XTDB/SQL:2011) | answers "true when?" *and* "known when?" | Graphiti couples it to an LLM | **KEEP** | `Fact.valid_from/valid_to` + `tx_from/tx_to`; `temporal/` predicates; tested CASO1/CASO2 |
| 2 | **Invalidate-don't-delete** supersession (Graphiti, Datomic) | preserves point-in-time history | needs discipline vs delete | **KEEP** | `supersede`/`correct_validity`/`retract` close belief, never delete |
| 3 | **LLM on the write path** (Graphiti, Mem0, GraphRAG, Cognee, Letta, TrustGraph) | rich extraction | non-deterministic, costly, cloud-bound, poisonable | **REJECT** | `NullModelProvider`; core CRUD/temporal/graph never call a model |
| 4 | **Ontology-validated extraction gate** (Cognee) | raises graph quality | LLM-dependent as shipped | **MODIFY** | caller supplies validated triples; engine enforces validation + provenance contract; LLM gate optional via `ModelProvider` |
| 5 | **PROV Entity/Activity/Agent** (W3C PROV; TrustGraph) | portable, queryable genealogy | PROV has no valid-time | **KEEP + EXTEND** | `provenance/` maps object→Entity, ledger event→Activity, agent→Agent; `explain()`; ADR-004 |
| 6 | **Named-graph separation of facts vs provenance vs explainability** (TrustGraph) | clean, interoperable | RDF stack heavy | **MODIFY** | logical separation: facts (objects) / provenance (ledger + edges) / retrieval explainability (`why_returned`) |
| 7 | **Content hashing / tamper evidence** (event sourcing; *absent in all competitors*) | detect history tampering | not "immutable" without anchor | **KEEP + EXTEND** | `ledger/` hash chain + `verify_chain(expected_head)`; ADR-009 |
| 8 | **Explainable retrieval** (GraphRAG context records, TrustGraph DAG, Cognee typed enum) | trust over opaque similarity | — | **KEEP** | `retrieval/` returns `score_components`, `why_returned`, `temporal_state`, `source` |
| 9 | **Hybrid retrieval** semantic+BM25+graph (Graphiti) | recall + precision | vector needs a model | **MODIFY** | deterministic lexical+structural+temporal+authority now; vector/ANN as an optional pluggable port (ADR-007) |
| 10 | **Memory-as-tools, state-in-store** (Letta) | portable, inspectable, stateful | destructive in-place edits | **KEEP (model) / REJECT (destructive)** | MCP tool surface + engine API; append-only bitemporal instead of in-place |
| 11 | **Operation taxonomy** add/update/delete/noop (Mem0) | inspectable vocabulary | LLM as arbiter; hard delete | **MODIFY** | deterministic `assert/supersede/correct_validity/retract/contradict/confirm`; no delete |
| 12 | **Decisions as first-class queryable nodes + precedent search** (Semantica) | auditable decision lineage | — | **KEEP (+ v0.2 precedent search)** | `Decision` + `explain(decision)`; precedent search noted for v0.2 |
| 13 | **Hexagonal ports & adapters** (ABI) | infra-swappable, model-agnostic | can hide heavy prod stack | **KEEP** | `storage/ports.py`; `CORE ← ADAPTER`; ADR-006/013 |
| 14 | **Community summaries (Leiden)** (GraphRAG) | corpus-wide "global" answers | frozen LLM summaries baked into truth | **MODIFY (defer)** | structure noted as an optional *derived* view over the ledger; not in v0.1 core |
| 15 | **Local-first embedded stores** (Cognee, ABI, MCP memory) | privacy, no infra | — | **KEEP** | single SQLite file (WAL); in-memory adapter; no server |
| 16 | **Fail-closed multi-tenancy** (*weak in all competitors*) | prevents cross-tenant leak/poison | must be designed in, not added | **KEEP + EXTEND** | `identity/` Principal; store-level scope filter; ADR-008 |
| 17 | **"Memory is an injection sink"** (MCP memory analysis) | correct threat framing | — | **KEEP** | ingested content is inert data; never executed/dereferenced; THREAT_MODEL S1/S2 |
| 18 | **Soft `group_id` / opt-in access control** (Graphiti, Cognee) | convenient | leaks across tenants | **REJECT** | isolation is mandatory + fail-closed |
| 19 | **Cloud / egress by default** (Graphiti, Mem0, TrustGraph, ABI) | easy hosted UX | breaks sovereignty | **REJECT** | zero-egress core, proven by socket-trap test |
| 20 | **Backend sprawl** (Semantica: 4 RDF+4 LPG+5 vector; TrustGraph fleet) | broad demos | shallow support, no unified consistency | **REJECT** | deep on one embedded store; add backends only on measured need (mission §39) |
| 21 | **RDF-star / classic reification** for statement metadata (PROV survey) | statement-level metadata | RDF-star redesigned for RDF 1.2 (CR) — migration landmine | **REJECT (for now)** | metadata carried on the object/envelope; PROV-O *export* is the interop path, not the storage model |

## Net

EPISTEMOS keeps the field's genuinely good ideas (bitemporality, invalidate-don't-delete, PROV
genealogy, explainable retrieval, memory-as-tools, hexagonal ports, local-first) and rejects the
field's shared mistakes (LLM-on-write, cloud-by-default, soft tenancy, hard delete, provenance
severed at ingest, backend sprawl). Its **novel** contributions are the combination plus a
**content-hashed tamper-evident ledger** and **fail-closed tenancy** that no surveyed system has.
