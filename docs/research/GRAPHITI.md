# Graphiti (+ Zep)

**Identity (MEASURED):** `github.com/getzep/graphiti`, **Apache-2.0**, Python 3.10+
(`graphiti-core` on PyPI). The OSS temporal knowledge-graph engine that also powers Zep's
proprietary hosted "Context Lake" agent-memory product. Backends: Neo4j / FalkorDB / Neptune /
Kuzu (embedded, deprecated).

**Temporal (MEASURED) — the flagship idea:** every fact is a graph **edge carrying four
timestamps**: `valid_at`/`invalid_at` (valid time) **and** `created_at`/`expired_at`
(transaction time). Supersession is done by **INVALIDATION, not deletion** — the old edge stays
for point-in-time queries. This bitemporal edge is the single most reusable primitive in the
whole census.

**Provenance (MEASURED):** strong episodic lineage — every entity/edge references the raw
"episode" node(s) it came from (`MENTIONS`). But: episode-granularity only, **no content
hashing, no signatures, no PROV**; and the stored `fact` is an **LLM paraphrase** of the source,
not a verbatim span.

**Retrieval (MEASURED):** hybrid (cosine + BM25 + graph BFS) with pluggable rerankers (RRF, MMR,
node-distance, episode-mention). Partly explainable (temporal validity + source episodes visible;
fusion scores less so).

**LLM / cost (MEASURED):** **HIGH and mandatory** on the write path — per episode it issues
multiple LLM calls (extract entities, extract edges, dedup, contradiction/invalidation, summaries)
plus mandatory embeddings. Not zero-egress, not deterministic, quality degrades on weak/local models.

**Security (MEASURED):** multi-tenancy is **soft** — `group_id` is an application-level filter,
not enforced isolation; ingested episodes are untrusted text driving graph mutations (poisoning).

## What it got right (KEEP)
Bitemporal per-edge model · invalidate-don't-delete · episodic provenance layer · hybrid retrieval
with rerankers · incremental (non-batch) construction.

## What we reject
LLM-mandatory write path · LLM-as-judge invalidation with no persisted evidence chain ·
cloud egress by default · soft `group_id` tenancy · destructive LLM regeneration of summaries.

## The one lesson for EPISTEMOS
Adopt the bitemporal edge + invalidate-don't-delete **wholesale**, then **decouple it from the
LLM**: drive supersession/invalidation with deterministic operations, not a model.

## How EPISTEMOS differs
Bitemporal core with **no LLM in the critical path** (deterministic `supersede`/`correct_validity`/
`retract`), **fail-closed** tenant/namespace isolation (not a string filter), a **tamper-evident
hash-chained ledger** with content hashes, and PROV-style genealogy Graphiti lacks.
