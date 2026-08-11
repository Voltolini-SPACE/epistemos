# ADR-010 — Security boundary: content is inert data; fail closed

**Status:** Accepted (v0.1)

## Context
The census's sharpest lesson: **memory is an injection sink** — anything written is later replayed
into a model as trusted context. Systems that feed ingested text to an LLM on the write path, or
dereference URIs, or trust recalled content as instructions, are self-reinfecting attack channels.

## Decision
The core treats **all ingested content as inert data**: it is never executed, never interpreted as a
query (no Cypher/SPARQL/SQL surface — SQL is fully parameterized), never fed to a model by the core,
and URIs are **never dereferenced** (SSRF closed by construction; zero-egress). Inputs are validated
and bounded (size, JSON depth, control chars, mime allow-list, finite confidence, strict timestamps).
The engine is **fail-closed**: unknown tenant/auth/source/schema/integrity ⇒ refuse (mission §26).
Network interfaces (REST/MCP) are hostile boundaries: identity is server-side, MCP exposes only a
fixed narrow tool allow-list, REST binds localhost. See `docs/security/THREAT_MODEL.md` (S1–S50).

## Consequences
- Whole classes of attack (injection, SSRF, prompt injection, deserialization) are closed by design.
- Some convenience (auto-fetching a source URI, LLM auto-extraction) is deliberately not provided by
  the core; those are opt-in enrichments behind explicit, authorized components.

## Rejected alternatives
- **LLM on the write path** (Graphiti/Mem0/…): turns untrusted input into a poisoning surface; rejected.
- **Auto-dereferencing source URIs**: SSRF; rejected.
- **Trusting recalled content as instructions**: the core never does — it returns data.
