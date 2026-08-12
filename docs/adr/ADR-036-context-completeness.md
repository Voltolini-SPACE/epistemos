# ADR-036 — Honest context completeness (`context_incomplete`)

**Status:** Accepted (v0.6.0)

## Context

A compact context is only trustworthy if it tells the truth about what it left out. A silent
truncation is worse than a large context: the agent reasons as if it saw everything. The failure
mode we must never ship is "looks complete, isn't."

## Decision

Every envelope carries a boolean `context_incomplete` and a sorted, deduplicated list
`incomplete_reasons` drawn from a fixed vocabulary:

| reason | when |
|---|---|
| `history_collapsed` | superseded versions were folded (recoverable via a group handle) |
| `token_limit` | experimental budget packing dropped items |
| `continuation_available` | an experimental continuation handle is offered for dropped items |
| `evidence_unavailable` | referenced evidence could not be materialized |
| `authorization_limited` | a related object exists but is not readable by this principal |

Rules:

- A **true-duplicate** collapse is *not* an omission (bit-identical content, both ids reachable) →
  it does **not** set `context_incomplete`.
- A **history** collapse *is* an omission from the inline view (though reachable) → it sets the flag
  with `history_collapsed`.
- Forcing `context_incomplete = False` is a non-equivalent mutation and is killed by the test suite
  (M5).

## Consequences

- A consumer can always distinguish "this is everything" from "this is a compacted view; here is why
  and here are the handles to recover the rest."
- `reachable_ids()` plus `incomplete_reasons` together make every omission recoverable and
  explained.

## Alternatives rejected

- **Silent truncation** — the exact anti-pattern this ADR exists to forbid.
- **A free-text note** — not machine-checkable; agents cannot branch on it reliably.
