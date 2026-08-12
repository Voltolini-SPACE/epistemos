# EPISTEMOS — Experimental History

A product's negative results are part of its evidence. This index records what was tried, what was
hypothesized, what the measurements showed, and what shipped — so nothing rejected looks shipped, and
nothing shipped looks unproven. Research branches are preserved, never deleted.

| # | Idea | Hypothesis | Result | Decision | Shipping status |
|---|---|---|---|---|---|
| **06** | Dimensions / Resonance / Microconnections / Contextual Geometry | A richer, geometry-aware memory would beat a lean retrieval + envelope baseline | **Falsified.** No gain on a lean baseline; precision fell **0.67 → 0.20 at scale**; 6/7 signals Δ0; 0 token savings | **REJECT** | Not shipped. Branch preserved (`b0a8b1b`), not merged. |
| **07** | Evidence-Preserving Context Envelope | Pinning contradictions + collapsing only *safe* redundancy + honest incompleteness preserves recall while cutting tokens | **Proven** on a small corpus: −33% tokens, correctness/recall/contradictions = baseline, leak = 0 | **PROVE → promote** | Research branch preserved (`488645f`); promoted in v0.6. |
| **08** | Context Envelope at scale | The v0.7 result holds on a large redundant corpus (1000+ state changes) | **Confirmed.** −34.6%, stable ~35% at 100/500/2000 entities; all loss/leak gates 0; mutation 6/6 | **PROMOTE** | Shipped as `context/` in **v0.6.0**. |
| **09** | EPCTX/1 protocol | The envelope can become a stable, provider-agnostic consumption contract over SDK/REST/MCP without coupling the core to any consumer | **Confirmed.** Transport parity; leak invariants 0; injection stays data; mutation 7/7 | **PROMOTE** | Shipped as `protocol/` in **v0.7.0**. Integrations spec-only. |

## Principle

> Do not prove the idea. Test it.

EPISTEMOS-06 is the anchor: a whole class of "richer memory" ideas was tested honestly and rejected
before anything shipped. What survived (the Context Envelope, then EPCTX/1) earned its place by
measurement, not by sounding good. The Dimensions work remains **REJECTED / RESEARCH** — it is not a
feature, was never merged, and must never be presented as shipped.

Detailed research: `docs/research/` (competitor census, feature harvest, final report). Per-mission
freeze evidence: `docs/EPISTEMOS_V0_*_FINAL_REPORT.md` and `docs/STATUS.md`.
