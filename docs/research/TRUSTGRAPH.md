# TrustGraph

**Identity (MEASURED):** `github.com/trustgraph-ai/trustgraph`, **Apache-2.0**, Python (+ TS client/
UI). Positioned as a "deterministic context engineering platform". Local inference supported
(vLLM/Ollama/TGI/LM Studio/Llamafile). Heavy footprint: message broker + Cassandra + Qdrant + object
store + N processors.

**Provenance (MEASURED) — the standout idea:** provenance-first using **distinct RDF named graphs**
— *facts* / *extraction-lineage* / *retrieval-explainability* — so lineage and reasoning are
first-class, queryable, and **W3C PROV-O compatible**, without polluting the knowledge layer. Every
node/edge traces source document → page → chunk.

**Retrieval (MEASURED):** **explainable-by-construction** — every answer emits the exact grounding
subgraph + a four-stage reasoning trail (Grounding / Exploration / Focus / Synthesis) as a visual DAG.
Standards-aligned (RDF/OWL/SKOS/SHACL, Turtle import/export).

**Temporal (MEASURED):** **absent** — no valid-time/transaction-time, no supersession/invalidation, no
as-of; facts silently go stale.

**LLM / cost (MEASURED):** LLM extraction is **mandatory at ingest** (cost/latency scale with tokens;
prompt-injection in a source doc can poison the graph). Cloud model APIs are the default adapter path.

**Ops (MEASURED):** multi-service "operating system" footprint with **no unified transaction/crash-
consistency layer** — a processor failing mid-flow leaves facts, vectors, and provenance out of sync.

## What it got right (KEEP)
Provenance-first, PROV-O-compatible · **named-graph separation of facts vs provenance vs
explainability** · explainable retrieval that emits the grounding subgraph + reasoning trail ·
storage/model-agnostic incl. local inference · semantic-web alignment for portability.

## What we reject
Mandatory LLM extraction at ingest · cloud LLM as default · heavy distributed footprint with no unified
consistency layer · **no bitemporal model** · provenance-by-reference without source hashing/signing.

## The one lesson for EPISTEMOS
**Separate provenance from facts** (distinct layers) and make **every retrieval emit its grounding +
reasoning path**. EPISTEMOS already keeps provenance edges + `explain()`; the harvestable refinement
is a distinct, queryable *retrieval-explainability* record and PROV-O export.

## How EPISTEMOS differs
A single **embeddable, crash-consistent** core (one transaction boundary) instead of a broker+Cassandra
+Qdrant fleet; **bitemporal** from day one; **content-hashed** provenance in a tamper-evident ledger;
deterministic ingestion with untrusted text treated as inert data.
