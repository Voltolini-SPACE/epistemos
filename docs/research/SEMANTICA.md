# Semantica

**Identity (MEASURED):** `github.com/semantica-agi/semantica` (formerly `Hawksight-AI/semantica`,
301-redirect; LICENSE © 2026 Hawksight AI). **MIT**. Python 3.8+. `pip install semantica`.
~v0.6.5, created 2025-06-25. Docs: docs.getsemantica.ai. Positioned as "Open Source Palantir".

**Architecture (MEASURED):** a *deterministic* pipeline —
Sources→Ingest→Parse→Normalize→Split→Extract→Conflict-Detection→Dedup→KG→
[Ontology · Reasoning · Provenance · Decisions]→(Vector + polyglot store)→Export/REST/MCP/CLI.
Polyglot backends: RDF (Oxigraph/Blazegraph/Jena/RDF4J) + LPG (Neo4j/FalkorDB/AGE/Neptune) +
vectors (FAISS/Qdrant/Weaviate/Milvus/Pinecone).

**Temporal:** README **CLAIMS** bi-temporal (valid vs recorded time) + point-in-time snapshots.
The researcher could **not** verify the depth of this in code/docs → treat as CLAIM, not MEASURED.

**Provenance (MEASURED):** W3C **PROV-O** on every fact, exportable JSON/CSV/RDF; SHACL/OWL/SKOS
governance. Conflicts are **flagged, not silently overwritten**.

**Retrieval / reasoning (MEASURED):** forward-chaining, Rete, Datalog, SPARQL; graph traversal +
vector + GraphRAG + **precedent search**. **No LLM required** for graph/reasoning (pattern
extraction is default; LLM optional).

**Decisions (MEASURED):** decisions stored as **first-class, queryable graph nodes** with causal
ancestry and PROV-O lineage.

## What it got right (KEEP)
- Deterministic, LLM-optional pipeline with provenance (PROV-O) and conflict-flagging — the same
  thesis EPISTEMOS holds.
- **Decisions as first-class queryable nodes + precedent search** — the distinctive idea.
- Embedded local store option (Oxigraph) proving local-first is feasible.

## What we reject
- **Backend sprawl** (4 RDF + 4 LPG + 5 vector + Databricks/Snowflake at v0.6): breadth over depth
  invites shallow support and correctness debt. EPISTEMOS goes **deep on one embedded store**.
- Cloud connectors that contradict zero-egress — must be hard-gated, off by default.
- Over-claiming: promotional-inflation signals (org churn, junk mirror org, "Palantir" framing,
  odd 522-fork/34-watcher ratio). **Verify by measurement, pin a canonical SHA** if ever depended on.

## The one lesson for EPISTEMOS
Record the **decisions themselves** as retrievable, auditable objects with causal lineage and
*precedent search* — not just the facts. EPISTEMOS already models `Decision` with evidence +
`explain(decision)`; **precedent search over prior decisions** is the natural v0.2 extension.

## How EPISTEMOS differs
EPISTEMOS makes bitemporality **MEASURED and tested** (not a README claim), keeps a single
crash-consistent embedded store instead of a polyglot fleet, and enforces fail-closed tenancy +
a tamper-evident ledger that Semantica's provenance layer does not provide.
