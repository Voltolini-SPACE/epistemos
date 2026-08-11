# Mem0

**Identity (MEASURED):** `github.com/mem0ai/mem0` (~40k stars), **Apache-2.0** OSS core
(`mem0ai` on PyPI); separate commercial hosted "Mem0 Platform" (api.mem0.ai). Python + TS.

**API (MEASURED) — the good part:** a small, uniform surface — `add / search / get / update /
delete / history` — hiding the storage backends. Pluggable and storage-agnostic (many vector
stores, several graph stores, many LLM/embedder providers incl. fully local Ollama/FAISS/Qdrant/
Kuzu → a zero-egress deployment is *possible*). Identity scoping via `user_id`/`agent_id`/`run_id`.

**Temporal (MEASURED):** **none** beyond `created_at`/`updated_at` (transaction-time only). Cannot
answer "what did we believe at T" or "when was this true in the world".

**Provenance (MEASURED):** **severed at ingest** — an LLM paraphrases messages into fact strings
with no source id, offset, or content hash; claims can't be traced or re-verified.

**The core anti-pattern (MEASURED):** an LLM is the **sole, non-deterministic arbiter** of
ADD/UPDATE/DELETE **in the write path**. Contradictions trigger a **destructive UPDATE/DELETE**
instead of bitemporal invalidation → permanent knowledge loss, no as-of history, and an
attacker-controlled-text → memory-rewrite/erase surface.

## What it got right (KEEP)
Small uniform API · storage/model-agnostic (local possible) · the **ADD/UPDATE/DELETE/NOOP operation
taxonomy** as an inspectable *proposal* vocabulary · identity scoping fields · a change-history concept.

## What we reject
LLM as sole non-deterministic write-path arbiter · physical DELETE/overwrite of contradicted facts ·
provenance-free paraphrase storage · cloud-egress-by-default hosted path · tenancy as a filter field.

## The one lesson for EPISTEMOS
**Invert the write path.** Keep Mem0's clean operation *vocabulary* (add/update/supersede/retract),
but make the arbiter **deterministic and reversible**, capture the **verbatim** input with a hash,
and **invalidate, never delete**.

## How EPISTEMOS differs
Deterministic operations (`assert`/`supersede`/`correct_validity`/`retract`/`contradict`/`confirm`)
that **never hard-delete**; bitemporal history; every observation stored with a `source_hash`;
enforced tenant/agent isolation instead of a scope field.
