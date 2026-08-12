# ADR-041 — EPCTX prompt renderer (adapter; data is not instruction)

**Status:** Accepted (v0.7.0)

## Context

EPCTX is structured; models often want text. But turning a document into a prompt risks two failures:
the envelope becoming a giant prompt by default, and evidence text acting as instruction.

## Decision

Provide an **optional** renderer (`render`, `render_prompt`) with three styles (compact / balanced /
audit). It is an adapter, never the default representation. The rendered CONTEXT region is fenced
under a banner declaring it data, not instructions; `render_prompt` assembles SYSTEM / CONTEXT / USER
with hard boundaries so only SYSTEM and USER carry instructions. Evidence text is copied verbatim and
never interpreted (§15, §29).

## Consequences

- `PROMPT_INJECTION_DATA_ONLY` holds: evidence saying "ignore previous instructions" renders as a
  quoted datum inside the fence (`test_prompt_injection_in_evidence_stays_data`).
- Rendering is lossy by design; the structured document stays the source of truth.

## Alternatives rejected

- **Render by default / only text** — loses structure and the safety fields; invites injection.
