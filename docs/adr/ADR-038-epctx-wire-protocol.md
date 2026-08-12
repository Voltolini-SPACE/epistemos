# ADR-038 — EPCTX/1 wire protocol (DTO separate from the internal model)

**Status:** Accepted (v0.7.0)

## Context

The Context Envelope (v0.6) made compact context an in-process value. To let *any* agent consume
EPISTEMOS — local, REST, MCP, Claude- or OpenAI-based, custom — without coupling the core to any of
them, the context needs a **stable wire contract**, distinct from the evolving internal model.

## Decision

Define **EPCTX/1**, a JSON wire document produced by a projection layer (`epistemos.protocol`) over
the internal `ContextEnvelope`. The core model may evolve; the projection keeps EPCTX/1 stable while
the semantics hold (`INTERNAL_MODEL_CHANGE` does not break `EPCTX/1`).

- Sections by object type (facts/claims/evidence/reviews/decisions/sources); contradictions a
  separate section; explicit `belief_state`/`accepted_state` so a claim is never a fact; temporal,
  provenance, completeness, token accounting, integrity, and (experimental) expansion.
- Surfaced additively: `engine.epctx()`, SDK `.context()`, REST `POST /context`, MCP
  `epistemos_context`. `engine.search` and `engine.context` are unchanged (§33).
- **Identity is server-side** on every transport; request bodies / tool args never carry authority.

## Consequences

- A new `protocol` package and three thin transport adapters; no new store/index/cache.
- The internal envelope can change without breaking consumers, as long as the projection holds.
- Full transport parity is a freeze gate (local == REST == MCP).

## Alternatives rejected

- **Expose internal classes directly** — couples consumers to internals; every refactor breaks them.
- **A different schema per transport** — divergent semantics; no single contract.
