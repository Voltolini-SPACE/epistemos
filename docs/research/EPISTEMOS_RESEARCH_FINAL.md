# EPISTEMOS — Final Research Report

Synthesis of the 2026-08-11 state-of-the-art census (mission §42). Full per-system detail lives in
the sibling files; this is the compact, decision-oriented summary. Every external claim is tagged
CLAIM / MEASURED in the source docs.

## What each system got right (and we kept)

- **Semantica** — deterministic, LLM-optional pipeline with PROV-O provenance; **decisions as
  first-class queryable nodes** with precedent search. (Its bitemporal *claim* is unverified.)
- **Graphiti / Zep** — the **bitemporal edge** (valid-time + transaction-time) with
  **invalidate-don't-delete** supersession, each fact tied to its source. The best primitive in the field.
- **Microsoft GraphRAG** — hierarchical **community structure** for corpus-wide "global" questions,
  and inspectable **context records**; proof a graph-RAG engine can run on local file stores.
- **Cognee** — **ontology-validated extraction** as a quality gate; a **typed retrieval enum**;
  storage-agnostic adapters; an embedded local-first default stack.
- **Mem0** — a **small uniform API** and an inspectable **operation taxonomy** (add/update/delete/noop);
  identity-scoping fields; local backends make zero-egress *possible*.
- **Letta / MemGPT** — **memory-as-explicit-tools** and the **"state lives in the store, not the
  client"** invariant; clear in-context/out-of-context tiering; provider-agnostic portability.
- **TrustGraph** — **provenance-first** with PROV-O and **named-graph separation** of facts vs lineage
  vs explainability; retrieval that emits its **grounding subgraph + reasoning trail**; local inference.
- **ABI / Naas** — **hexagonal ports & adapters** (typed model at the center, swappable infra) and a
  genuine no-Docker local mode; SPARQL-over-typed-graph as the explainable path.
- **Standards & temporal DBs (W3C PROV, XTDB/Datomic, MCP memory)** — separate the two time axes;
  keep an immutable log with a rebuildable projection; make provenance a first-class graph; and treat
  **memory as an injection sink** where all recalled content is untrusted data.

## What we rejected, and why

| Rejected pattern | Seen in | Why EPISTEMOS refuses it |
|------------------|---------|--------------------------|
| **LLM on the write/CRUD path** | Graphiti, GraphRAG, Cognee, Mem0, Letta, TrustGraph | non-deterministic, costly, cloud-coupled, and turns untrusted input into a memory-poisoning surface. Core is deterministic; the model is optional enrichment behind `ModelProvider`. |
| **Hard delete / in-place overwrite** of contradicted facts | Mem0, Letta | destroys history and audit. EPISTEMOS invalidates/supersedes; there is no delete API. |
| **Provenance severed at ingest** (LLM paraphrase, no source/hash) | Mem0, Letta, Graphiti (partial) | claims can't be traced or re-verified. Every observation stores a `source_hash`; facts link to sources/derivation. |
| **Cloud / egress by default** | Graphiti, Mem0, TrustGraph, ABI | breaks sovereignty. Core is zero-egress, proven by a socket-trap test. |
| **Soft / opt-in tenant isolation** (`group_id`, scope field) | Graphiti, Cognee, MCP memory | leaks and poisons across tenants. Isolation is mandatory and fail-closed. |
| **Backend sprawl** (many half-supported stores) | Semantica, TrustGraph | shallow support, no unified consistency. One embedded store, deep; more only on measured need. |
| **LLM-generated query languages** (LLM→SPARQL/Cypher) | ABI, Cognee | injection + over-broad-query surface. EPISTEMOS exposes typed method calls; there is no query language to inject into. |
| **Immutability mistaken for safety** | event-sourcing naïveté | a poisoned append-only fact is *permanently* trusted. We pair the append-only ledger with write-time provenance, trust, and supersession. |

## What EPISTEMOS does differently (the thesis)

The census's most consistent finding is that the field couples memory to the LLM and treats provenance,
time, and tenancy as afterthoughts. EPISTEMOS inverts all three:

1. **Deterministic bitemporal core, LLM-optional.** Every fundamental operation runs with
   `NullModelProvider`; bitemporality (valid + transaction time) is a *tested* core model, not a claim.
2. **Provenance-first and tamper-evident.** A hash-chained, append-only event ledger is the source of
   truth; the queryable state is a pure, rebuildable projection of it. `explain()` walks a PROV-style
   genealogy. **No surveyed competitor content-hashes its provenance.**
3. **Fail-closed, multi-tenant by construction.** Tenant/namespace/agent scope every read and write;
   unknown scope is refused. Ingested content is inert data, never instructions, never dereferenced.
4. **Local-first, zero-egress, storage-agnostic.** One SQLite file or in-memory; the domain depends on
   ports, not on any specific graph/vector DB; the core has **zero third-party runtime dependencies**.

EPISTEMOS is the composition of the field's best ideas with the field's mistakes designed out — plus
two properties (content-hashed tamper-evidence and fail-closed tenancy) that none of the surveyed
systems provide. It is a **clean-room** implementation: concepts were learned; **no code was copied**
(see [`../security/LICENSE_MATRIX.md`](../security/LICENSE_MATRIX.md)).
