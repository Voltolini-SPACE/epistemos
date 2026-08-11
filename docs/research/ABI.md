# ABI (Agentic Brain Infrastructure) / Naas.ai

**Identity (MEASURED):** `github.com/jupyter-naas/abi` (NaasAI with OpenTeams, University at Buffalo/
NCOR, Forvis Mazars). **MIT**. Python 3.12+ (+ TS frontend). PyPI: `naas-abi`. Genuine dev/local mode:
bundled **Oxigraph + SQLite + sqlite-vec + filesystem, no Docker required**.

**Model (MEASURED) — the standout idea:** a shared, standards-based **top-level ontology (BFO /
ISO 21838-2)** as the substrate for *all* memory. Retrieval becomes **typed, SPARQL-queryable,
explainable reasoning** instead of opaque vector similarity. Because storage sits behind **hexagonal
ports & adapters**, the same typed graph survives swaps of LLM, vector DB, and object store.

**Retrieval (MEASURED):** hybrid symbolic (SPARQL over the typed graph) + vector, with agentic source
routing — the symbolic path is the explainable one.

**Temporal (MEASURED):** **not native** — valid-time/transaction-time/supersession/as-of must be
hand-modeled as reified triples (fragile, easy to get wrong).

**Provenance (MEASURED):** **compliance narrative, not enforcement** — BFO grounding + ISO 42001/EU
AI Act framing is marketing, *not* an enforced per-fact lineage + evidence-hash layer.

**Security (MEASURED):** LLM-generated SPARQL is an **unmitigated injection + over-broad-query
surface** (needs allow-listing, cost/row caps, read-only scoping). Default hard dependency on an
external OpenAI-compatible LLM breaks zero-egress.

## What it got right (KEEP)
BFO/ISO-21838-2 typed ontology substrate (explainable, standards-based) · **hexagonal ports &
adapters** (storage/model-agnostic by construction) · SPARQL-over-typed-graph as the explainable path ·
genuine no-Docker local mode (Oxigraph + SQLite + sqlite-vec) · hybrid symbolic+vector retrieval.

## What we reject
Provenance-by-compliance-narrative · non-bitemporal storage (time offloaded to reified triples) ·
default external-LLM dependency · **unsandboxed LLM-to-SPARQL generation** · heavyweight prod stack
masquerading as local-first-simple.

## The one lesson for EPISTEMOS
The **hexagonal ports & adapters** discipline: put the typed model at the center and make every
backend (graph/vector/object/LLM) a swappable adapter — so the knowledge survives infra swaps.
EPISTEMOS already enforces `CORE ← ADAPTER`; ABI validates the pattern at production scale.

## How EPISTEMOS differs
No query-language surface to inject into (typed method calls, not LLM-generated SPARQL); native
bitemporality; **enforced** PROV-style lineage + content hashes rather than a compliance narrative;
zero-egress core with no LLM dependency by default.
