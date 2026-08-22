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
| **EPISTEMOS** | (this repo) | MIT | Python (stdlib-only) | event-sourced bitemporal core + ports |

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

Against **this tier**, EPISTEMOS is the only design that is *simultaneously* bitemporal,
deterministic (no-LLM core), hash-anchored-provenance, fail-closed multi-tenant, explainable, and
local-first zero-egress — see [`FEATURE_HARVEST.md`](FEATURE_HARVEST.md) and
[`EPISTEMOS_RESEARCH_FINAL.md`](EPISTEMOS_RESEARCH_FINAL.md).

That is **not** a claim of uniqueness in the field. It is a claim about the systems above, and the
distinction was missed in the original census — see the second tier below.

---

## Tier 2 — the peer group (added 2026-08-22)

The census above surveyed the large, well-funded LLM-native systems and concluded exclusivity.
That conclusion was **wrong as stated**: a cluster of smaller projects makes the same combination
of claims — bitemporal, provenance-first, local-first or self-hosted, MCP-native, no mandatory
LLM. All were created in 2026 and all were actively pushed within weeks of this census. Stars,
licences and dates are from the GitHub API on **2026-08-22** and move over time.

| System | Repo | ★ | Created | Lang | License | Declared pitch |
|---|---|--:|---|---|---|---|
| **Statewave** | smaramwbc/statewave | 317 | 2026-04-24 | Python | Apache-2.0 | Reproducible, provenance-tagged **context bundles** instead of query-time retrieval |
| **Mnemos** | klarlabs-studio/mnemos | 4 | 2026-04-12 | Go | MIT | Self-hosted memory + evidence layer; evidence-backed claims, bitemporal recall |
| **Talamus** | ampres-ai/talamus | 3 | 2026-06-09 | Python | Apache-2.0 | Cited Markdown, bitemporal history, review-gated correction, no hosted account |
| **Verimem** | aureliocpr-ctrl/verimem | 2 | 2026-07-04 | Python | AGPL-3.0 | Gated writes, provenance on every read, abstention instead of hallucination |
| **Cormex** | weironz/cormex | 0 | 2026-08-14 | Rust | Apache-2.0 | "Memory that remembers what you used to believe" — bitemporal, MCP-native |
| **Mneme** | BrettNye/Mneme | 0 | 2026-05-27 | TypeScript | — | Append-only claim ledger with supersession, provenance, deterministic replay |
| **EPISTEMOS** | Voltolini-SPACE/epistemos | 0 | 2026-08-12 | Python | MIT | Sovereign context, memory, provenance and decision lineage |

**Method caveat, stated plainly:** tier-1 capability cells are MEASURED from repos and docs.
Tier-2 pitches are **CLAIM** — the projects' own descriptions, read but not verified in code.
Do not present a tier-2 row as a measurement (mission §6).

### What this tier changes

- **Statewave is the only peer with traction**, and its lead is packaging rather than architecture:
  PyPI and npm SDKs (sync *and* async), a one-line `npx` install, Docker Compose and Helm, Swagger
  docs, connectors (GitHub, Slack, Notion, Zendesk, Gmail), LangChain/CrewAI/AutoGen integrations,
  a separate runnable-examples repository, and a published limitations section. On rigour it is
  *behind*: its own documentation states it cannot yet reproduce history byte-for-byte, which is
  precisely what EPISTEMOS's `as_of` + hash chain deliver.
- **Bitemporality and provenance are no longer differentiators** in this tier. They are the price
  of entry.
- **No peer models disagreement.** Every one of them stores *memory*: one agent, one truth, one
  history. None separates claim from evidence from review, derives belief at read time rather than
  storing it, or governs which assertions become accepted knowledge. That is the axis where
  EPISTEMOS still has no peer, it is the axis the mutation battery already proves
  (`docs/security/MUTATION_REPORT.md`), and it is the axis that maps to audit and compliance
  buyers rather than to chatbot personalization.

**Consequence for messaging:** retire "the only system that…". Lead with *governed multi-party
knowledge* — claims, disputes, evidence and acceptance governance — and let bitemporality and
provenance be table stakes that EPISTEMOS happens to implement more strictly. See
[`../KNOWN_LIMITATIONS.md`](../KNOWN_LIMITATIONS.md).
