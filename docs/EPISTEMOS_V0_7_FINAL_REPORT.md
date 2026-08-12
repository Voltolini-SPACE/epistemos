# EPISTEMOS v0.7.0 — EPCTX Protocol — Final Report

**Decision: `EPISTEMOS_V0_7_PASS`.** Tag `epistemos-v0.7.0`. v0.1.0–v0.6.0 + Panel v1 unchanged.

## What shipped

**EPCTX/1** — a stable, provider-agnostic **consumption protocol** for EPISTEMOS context. Any agent,
over any of three transports, reads the same document with the same semantics:

- **SDK** — `LocalContextClient` / `RemoteClient.context()`;
- **REST** — `POST /context` (+ `/context/expand`);
- **MCP** — the `epistemos_context` (+ `epistemos_context_expand`) tool.

The document (schema `EPCTX/1`) is a projection over the internal Context Envelope, kept stable while
the core model may evolve (ADR-038). It carries: objects **sectioned by type** with explicit
`object_type` + `belief_state`/`accepted_state` (a claim is never a fact); **contradictions in their
own section** + a `disputed` flag; **completeness** (`complete` + machine reasons); a **temporal**
contract (valid/transaction time, `is_current`, has-current/has-historical); **provenance** (per-object
source / derived_from / evidence_refs); **token accounting** (`token_estimate` + `tokens_by_section` +
`tokenizer_profile`); an **integrity** hash over canonical JSON; and **experimental** opaque expansion
handles.

Additive: `engine.epctx()` / `engine.expand()`; `engine.search` and `engine.context` are unchanged.
Identity is server-side on every transport — the request body, tool args, query, and consumer profile
never carry authority.

## Answers to the mission's final questions (§45)

1. **Generic agent consumes without internals?** Yes — `GenericContextClient` + `GenericAgentHarness`,
   no EPISTEMOS internals, no framework dependency.
2. **Claim distinguishable from fact?** Yes — `object_type` + `belief_state` + `accepted_state`
   (mutation M1 killed).
3. **Contradictions explicit?** Yes — separate `contradictions` section + `disputed` (M2 killed).
4. **Context incompleteness detectable?** Yes — `completeness{complete,reasons}` (M3 killed).
5. **Provenance queryable?** Yes — per-object provenance + a document-level table (M5 killed).
6. **Temporal state clear?** Yes — per-object valid/tx time + `is_current`; document has-current/
   has-historical (M4 killed).
7. **REST/SDK/MCP equivalent semantics?** Yes — transport-parity test across current/historical/
   contradiction/decision queries and expansion.
8. **Prompt injection inside evidence stays data?** Yes — the renderer fences evidence under a
   data-only banner; SYSTEM/CONTEXT/USER boundaries are hard.
9. **Revocation blocks old expansions?** Yes — handles re-authorize live; forged/cross-principal/
   cross-tenant/revoked all yield nothing private (M6 killed).
10. **Works without NOMOS/Hermes/OpenClaw?** Yes — the whole suite runs with none of them imported;
    integration notes are spec-only.

## Gate evidence

| Gate | Result |
|---|---|
| Spec / serialization / versioning | canonical JSON deterministic; integrity self-consistent + tamper-detecting |
| SDK / REST / MCP + parity | equivalent documents across all three transports |
| Claim / contradiction / completeness / temporal / provenance preserved | all present and explicit |
| PRIVATE_EPCTX_LEAK / PRIVATE_EXPANSION_LEAK / CROSS_TENANT_EPCTX_LEAK | **0 / 0 / 0** |
| Prompt injection | stays data (fenced, never instruction) |
| Race (30×) / Chaos | clean; rebuild reproducible; degraded store = honest partial |
| Mutation | **7/7** killed; NON_EQUIVALENT_SURVIVED = 0 |
| Agent bench | EPCTX makes dispute + temporal + provenance reliably available; raw retrieval does not |
| Full regression | **996 passed**; ruff + mypy `--strict` clean |

Reproduce: `pytest tests/protocol`; `python tools/eps09_mutation.py`;
`python tools/eps09_agent_bench.py`.

## Boundaries held

EPISTEMOS returns context and **executes nothing**, grants no capability, mandates no provider, and
depends on no consumer. NOMOS, Hermes, OpenClaw, the Panel, and v0.1–v0.6 behaviour are unchanged;
integration is deferred to separate, opt-in missions. The protocol is **protocol-ready** and
**adapter-ready**, not integrated — proven independent first.

`STATUS_FINAL = EPISTEMOS_V0_7_PASS`.
