# ADR-033 — Context Envelope: compress the transmission, not the memory

**Status:** Accepted (v0.6.0)

## Context

An agent asking EPISTEMOS a question rarely needs the entire sovereign, bitemporal store — but it
does need the *right* objects, with their contradictions and provenance intact. Naively handing back
raw retrieval wastes context on superseded versions and exact duplicates; naively summarizing loses
the very evidence and contradictions that make the store trustworthy.

EPISTEMOS-06 tested four richer theories (Dimensions, Resonance, Microconnections, Contextual
Geometry) and **falsified** them — none beat the baseline; all were rejected. EPISTEMOS-07 isolated
the single mechanism that did help: preserve the evidence, collapse only provably-safe redundancy,
and be honest about any omission. EPISTEMOS-08 re-proved it on a large corpus (1000+ state changes)
before promoting.

## Decision

Add a **Context Envelope**: a *post-retrieval* transform (`epistemos.context`) that turns the
objects the current authorized retrieval already returned into an evidence-preserving compact
context, schema `EPCTX/1`.

- It **never widens** the candidate set and **never lowers** an authorization boundary. The only
  relation it follows — a claim's attached contradiction — is re-authorized via `is_readable`.
- It is **additive**: `engine.search` is unchanged; `engine.context(principal, query, compact=True)`
  is a convenience transform over it.
- **Stable** parts: contradiction pinning (ADR-035), intent-aware safe redundancy collapse
  (ADR-034), honest `context_incomplete` (ADR-036). **Experimental**, off by default: token-budget
  packing and continuation handles (ADR-037).

## Consequences

- One new module, one new engine method, one schema. No new store, index, or cache.
- Redundant, entity-focused retrievals cost measurably fewer tokens (~35% in measured scenarios,
  ADR names the honest scope) with zero evidence/contradiction/temporal loss.
- The transform is a pure function of `(authorized store state, query, intent)`; same input →
  identical envelope (chaos-reproducible).

## Alternatives rejected

- **Dimensions / Resonance / Microconnections / Contextual Geometry** — falsified in EPISTEMOS-06.
- **Lossy summarization** — discards evidence and contradictions; violates the trust model.
- **A new retriever** — would widen the candidate set and duplicate the authorization surface.
