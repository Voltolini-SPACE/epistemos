# ADR-040 — EPCTX completeness in the wire

**Status:** Accepted (v0.7.0)

## Context

A compact context is only safe if it tells the truth about what it omitted. This restates the v0.6
completeness discipline (ADR-036) as a first-class **wire** field so every consumer, on every
transport, sees it.

## Decision

Every EPCTX/1 document carries `completeness = { complete: bool, reasons: [...] }` with a fixed reason
vocabulary (`history_collapsed`, `token_limit`, `continuation_available`, `evidence_unavailable`,
`authorization_limited`). A true-duplicate collapse is not an omission and does not set it; a history
collapse or a budget drop does. A pinned contradiction filtered by authorization sets
`authorization_limited` rather than vanishing silently.

## Consequences

- A consumer that ignores completeness is making an auditable, testable mistake (§27).
- `disputed` is likewise an explicit boolean, so "this context is disputed" is a field, not an
  inference.

## Alternatives rejected

- **Implicit completeness** — silence reads as "nothing to know"; the exact failure to forbid.
