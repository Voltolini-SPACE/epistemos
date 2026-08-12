# ADR-044 — EPCTX versioning rules

**Status:** Accepted (v0.7.0)

## Context

A consumption contract lives or dies by its evolution rules. Consumers must keep working as the
protocol grows.

## Decision

`protocol_version = "EPCTX/1"`; compatibility by **major**. Required fields are fixed and may be
relied upon; everything else is optional. A consumer **must ignore** optional fields it does not
recognize (forward compatibility). Deprecated fields stay present within a major and are removed only
at the next major. Removing or repurposing a required field is breaking and allowed only in `EPCTX/2`
with its own ADR. The `versioning` module is the single authority (version string, required set,
compatibility function).

## Consequences

- An `EPCTX/1.x` producer can add optional fields without breaking `EPCTX/1` consumers.
- Strict consumers can `assert_required`; lenient consumers ignore unknown extras. Both are correct.

## Alternatives rejected

- **Fail on unknown fields** — freezes the protocol; no additive evolution.
- **No required set** — consumers cannot rely on anything; not a contract.
