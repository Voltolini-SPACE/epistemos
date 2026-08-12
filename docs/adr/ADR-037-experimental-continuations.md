# ADR-037 — Experimental: token-budget packing & continuation handles (off by default)

**Status:** Accepted (v0.6.0) — feature is **experimental**, disabled by default

## Context

EPISTEMOS-07 also explored fitting an envelope to a hard token budget and offering continuation
handles to page through what did not fit. These help, but they were not hardened at the same level as
pinning / collapse / completeness, and the EPISTEMOS-08 promotion gate deliberately shipped only the
proven core. Shipping an unproven mechanism *enabled* would repeat the EPISTEMOS-06 mistake.

## Decision

Include token-budget packing and continuation handles in the code, but **off by default**, behind
`EnvelopeConfig`:

- `budget_pack=False`, `token_budget=None`, `continuation=False` — default; the stable path never
  packs.
- When enabled, packing **may not** drop a pinned contradiction or a critical item (contradiction /
  current / decision roles are retained even over budget). Any drop sets `context_incomplete` with
  `token_limit` (and `continuation_available` when continuation is on).

The public docs and README describe these as experimental and do not cite numbers for them.

## Consequences

- The default `engine.context(...)` path is exactly the proven core.
- The experimental knobs are available for research and for callers who opt in with eyes open, under
  the same evidence-preservation invariants.
- Promotion of these to stable requires their own hardening pass (a future mission) with its own
  benchmark, security, race, chaos, and mutation gates.

## Alternatives rejected

- **Ship enabled** — unproven at scale; violates the "test it, don't sell it" discipline that
  EPISTEMOS-06 established.
- **Delete the code** — loses the EPISTEMOS-07 research; keeping it gated preserves it honestly.
