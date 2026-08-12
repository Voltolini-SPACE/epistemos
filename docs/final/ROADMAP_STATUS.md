# EPISTEMOS — Roadmap Status (Freeze 2026.08)

Three buckets, kept distinct so nothing planned looks shipped and nothing shipped looks unproven.
(The v0.3-era measurement roadmap in `docs/roadmap/` is preserved as history; this is the current
consolidated status.)

## SHIPPED (stable, on by default)

- Bitemporal core: append-only hash-chained ledger, rebuildable projection (v0.1–v0.2).
- Scale retrieval: FTS5 lexical index, provenance index (v0.2–v0.3).
- Knowledge Spaces + capability authorization, private-by-default (v0.4).
- Collaborative Claims: claim / evidence / review, derived belief, governed acceptance (v0.5).
- **Context Envelope**: evidence-preserving compaction (v0.6).
- **EPCTX/1 protocol**: SDK + REST + MCP, provider-agnostic (v0.7).
- **Panel v1.1**: operational UI, hardened.
- MIT, zero-egress core, no mandatory LLM, zero runtime dependencies.

## EXPERIMENTAL (in the code, off by default)

- Token-budget packing + continuation handles for the Context Envelope (ADR-037).
- EPCTX expansion handles (ADR-042) — opaque, principal/temporal-bound; not on the stable path.

## PLANNED / SPEC-READY (not built)

- Integrations: **NOMOS**, **Hermes**, **OpenClaw** — adapter specs only (`docs/integrations/`), no
  core dependency, no import. Real integration is a separate, opt-in mission.
- Optional external signing over the canonical EPCTX form (a port, not built).

## REJECTED (research, never shipped)

- Dimensions / Resonance / Microconnections / Contextual Geometry (EPISTEMOS-06) — falsified,
  branch preserved, not merged. See [`../research/EXPERIMENTAL_HISTORY.md`](../research/EXPERIMENTAL_HISTORY.md).
