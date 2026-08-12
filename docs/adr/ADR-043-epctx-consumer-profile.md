# ADR-043 — EPCTX consumer profile (advisory, no provider coupling)

**Status:** Accepted (v0.7.0)

## Context

Consumers differ: context windows, whether they want structured context, whether they need
provenance or decisions, whether they support expansion. The protocol must adapt to a consumer
without hardcoding a provider (no `provider=openai`).

## Decision

Accept an optional `consumer_profile` object (e.g. `max_context_tokens`, `prefers_structured_context`,
`supports_expansion`, `needs_provenance`, `needs_decisions`). It is **advisory** and **carries no
authority**. `max_context_tokens` may engage the experimental budget packer; the rest are hints. The
profile is echoed in `request.consumer_profile` for transparency.

## Consequences

- Provider-agnostic: no provider is named or required anywhere in the protocol (§12, §16).
- Identity is never taken from the profile; it is data, checked and bounded like any input.

## Alternatives rejected

- **Hardcode a provider / tokenizer** — couples the protocol to one vendor.
- **Let the profile set authority** — an injection and escalation vector.
