# Microsoft GraphRAG

**Identity (MEASURED):** `github.com/microsoft/graphrag`, **MIT**, Python ~3.10–3.12
(Microsoft Research). A batch **indexing pipeline** (documents → text units → LLM entity/
relationship/claim extraction → graph → Leiden community detection → LLM community reports) plus a
query engine (local / global / DRIFT search). Local file stores (LanceDB/Parquet/filesystem).

**Temporal (MEASURED):** **none** — no bitemporal model, no fact versioning, no "as of T", no
supersession. History exists only as manual folder copies.

**Provenance (MEASURED):** thin — chunk ids only; the load-bearing text is an LLM community
**summary**, not a verbatim span; no hashes, no evidence quotes, no cross-run lineage, no PROV.

**Retrieval (MEASURED):** genuinely novel — hierarchical **community summaries** answer corpus-wide
"global" questions that flat vector RAG cannot. Fuses vector + graph-neighborhood + community
context and returns inspectable context records (which entities/reports/units were used).

**LLM / cost (MEASURED):** LLM is **required to BUILD the graph**; cost scales with corpus size and
every rebuild yields a *different* graph. Community reports are **frozen at index time** → global
quality is capped by stale summaries.

## What it got right (KEEP)
Hierarchical community detection (Leiden) + community summaries as a real answer to *global* queries
(keep the **structure**, not the frozen summaries) · hybrid retrieval returning inspectable context
records · embedded local file stores (proves graph-RAG can run fully local) · pluggable storage/
vector/LLM seams + an LLM-call cache.

## What we reject
LLM as the graph builder / source of truth · baking non-deterministic LLM summaries into the
primary artifact · no temporal/versioning · provenance = chunk ids · cloud-egress default, no tenancy.

## The one lesson for EPISTEMOS
**Do not fuse the knowledge substrate with the LLM enrichment layer.** Keep a deterministic,
provenance-first, bitemporal core; let community-summary-style enrichment be an *optional, rebuildable*
view computed over it — never baked into the source of truth.

## How EPISTEMOS differs
EPISTEMOS's source of truth is a deterministic, hash-chained event ledger with a rebuildable
projection; any LLM enrichment (summaries, community structure) would be an optional derived layer
carrying its own provenance, not the primary artifact.
