# Letta / MemGPT

**Identity (MEASURED):** `github.com/letta-ai/letta` (formerly MemGPT; UC Berkeley Sky Lab; paper
"MemGPT: Towards LLMs as Operating Systems", 2023). **Apache-2.0** OSS framework + a separate managed
cloud. State persisted in **normalized relational tables**.

**Model (MEASURED) — the durable idea:** memory exposed as explicit, **model-invoked tools**
(`append`/`replace`/`search`) over a persisted, **provider-agnostic** state store. Agents are
stateful-by-construction and **portable across LLMs** ("state lives in the DB, not the client").
Clear tiering: bounded in-context **core** memory vs unbounded out-of-context **archival/recall**;
shareable memory blocks across agents.

**Temporal (MEASURED):** single time axis (`created_at`/`updated_at`); **not bitemporal**; no as-of,
no invalidation of facts that became false.

**Provenance (MEASURED):** agent-authored summaries stored as **ground truth** with no derivation
link back to source evidence — unfalsifiable, un-auditable.

**Security (MEASURED):** **self-editing memory** is a persistent prompt-injection / poisoning vector
— adversarial content can durably rewrite persona across sessions. `core_memory_replace` overwrites
in place, erasing superseded facts.

## What it got right (KEEP)
Memory-as-tools (inspectable, controllable) · fully-persisted state (survives restarts, no
serialization step) · provider-agnostic (port an agent across models) · clear in-context/out-of-context
tiering with overflow handling · shareable blocks for multi-agent state.

## What we reject
In-place destructive edits with no versioning/valid-time · provenance-free, hash-free storage of
derived assertions as truth · embedding-only opaque retrieval · deep per-op LLM dependency ·
self-editing memory with no trust/quarantine.

## The one lesson for EPISTEMOS
Keep the **"state lives in the store, not the client"** invariant and the **memory-as-explicit-tools**
surface — but replace destructive in-place edits with **append-only, bitemporal supersession**, and
require **provenance/trust tags** before content can enter durable memory.

## How EPISTEMOS differs
Append-only bitemporal facts with supersession (never overwrite); a hostile-boundary MCP tool surface
whose identity is **server-side** (a client cannot rewrite another scope's memory); every assertion
carries source + hash; explainable hybrid retrieval instead of embedding-only.
