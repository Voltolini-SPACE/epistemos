# ADR-042 — EPCTX expansion handles (opaque, bound, experimental)

**Status:** Accepted (v0.7.0) — feature is **experimental**, off the stable path

## Context

A consumer sometimes wants the collapsed members of a redundancy group. Exposing raw private ids up
front would leak; letting a token carry ids would let a consumer forge or retarget it.

## Decision

Offer **opaque expansion handles**. The token is a random id carrying nothing; the private ids it
stands for live in a per-engine server-side registry. Redemption (`engine.expand`) binds the handle
to the minter's identity (tenant / agent / namespace) and a temporal snapshot, re-checks the
presenting principal's fingerprint, and re-runs `is_readable` for every member **live** at the bound
snapshot. Capabilities are not baked in, so revocation takes effect immediately.

## Consequences

- `PRIVATE_EXPANSION_LEAK = 0` and `STALE_EXPANSION_PRIVATE_LEAK = 0`: forged, cross-principal,
  cross-tenant, and revoked handles all yield nothing private (no existence oracle).
- Experimental until its own hardening pass; not on the default path unless a consumer opts in.

## Alternatives rejected

- **Ids in the token** — forgeable, retargetable, leaky.
- **Bake capabilities into the handle** — revocation would not take effect at redemption.
