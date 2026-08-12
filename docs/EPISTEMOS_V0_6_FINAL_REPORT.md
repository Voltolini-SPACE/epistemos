# EPISTEMOS v0.6.0 — Context Envelope — Final Report

**Decision: `EPISTEMOS_V0_6_PASS`.** Tag `epistemos-v0.6.0`. v0.1.0–v0.5.0 + Panel v1 unchanged.

## What shipped

The **Context Envelope**: a post-retrieval transform that *compresses the transmission of memory,
never the memory*. `engine.context(principal, query, compact=True)` returns an `EPCTX/1` envelope
that:

- **pins contradictions** — retrieved, or attached to a retrieved claim (the attached case
  re-authorized per principal, so a private contradiction on a shared claim never leaks);
- **collapses only provably-safe redundancy** — superseded current-state versions (only for a
  confident "current" intent) and true duplicates (identical `content_hash`); corroboration and
  history are never folded;
- **preserves provenance** — every folded id and its lineage stay reachable behind a handle;
- **is honest** — any real omission sets `context_incomplete` with a machine-readable reason.

It is **additive**: `engine.search` is unchanged; the envelope never widens the candidate set and
never lowers an authorization boundary.

## The scientific arc (why only this)

- **EPISTEMOS-06** tested Dimensions, Resonance, Microconnections, Contextual Geometry — and
  **falsified** them. Rejected; branch preserved, not merged.
- **EPISTEMOS-07** isolated the one surviving mechanism (evidence-preserving compaction) and proved
  it on a small corpus. Ship candidate; branch preserved, not merged.
- **EPISTEMOS-08** (this release) re-proved it on a **large** corpus (1000+ state changes) as the
  hard promotion gate, then promoted only the proven core. Budget-packing and continuation handles
  ship **experimental, off by default** (ADR-037) — not sold, not benchmarked publicly.

## Gate evidence

| Gate | Result |
|---|---|
| CRITICAL_EVIDENCE_LOSS / CONTRADICTION_LOSS / TEMPORAL_REGRESSION | **0 / 0 / 0** at 1000+ changes |
| ANSWER_CORRECTNESS_DELTA | **+0.0** (100% → 100%) |
| TOKEN_REDUCTION | **+34.6%** (up to ~35% in measured redundant scenarios; **not** universal) |
| SCALE | stable **~35%** at 100/500/2000 entities; envelope latency linear in the pool |
| PRIVATE_CONTEXT_LEAK | **0** — private prior/contradiction/collapsed-member; cross-tenant/space; scale sweep |
| RACE (30×) | clean — 6 threads × 30 concurrent builds, two principals |
| CHAOS | reproducible — same store → byte-identical 5×; structural reproducibility across rebuilds |
| MUTATION NON_EQUIVALENT_SURVIVED | **0** — 6/6 killed (pin, history, attached-authz, provenance, incomplete, dup/corroboration) |
| FULL REGRESSION | **946 passed**; ruff + mypy `--strict` clean |

Reproduce: `python tools/eps08_benchmark.py --entities 250 --versions 4`, `--scale`;
`python tools/eps08_mutation.py`; `pytest tests/context`.

## Honesty notes (§28)

The token win is **not** universal. It applies to entity/fact-focused queries whose retrieval
returns version history (current-state and claim-history query types) over redundant corpora; broad
multi-entity lexical queries see little or no reduction. The published figure is always framed as
"up to ~35% in measured redundant scenarios," with runnable methodology.

## Surfaces

- New module `src/epistemos/context/` (`ContextEnvelopeBuilder`, `EnvelopeConfig`, `EPCTX/1`).
- New engine method `engine.context(...)` (additive; `compact=False` returns raw search).
- No new store, index, or cache. No REST/MCP surface in v0.6 (would bind principal server-side only).
- Docs: `docs/context/` (ARCHITECTURE, ENVELOPE_SCHEMA, REDUNDANCY_COLLAPSE, CONTRADICTION_PINNING,
  SECURITY, BENCHMARK, API); ADR-033…037.

## Untouched

NOMOS, Hermes, OpenClaw, the Panel, and v0.1–v0.5 behaviour are unchanged. The EPISTEMOS-06 and
EPISTEMOS-07 research branches are preserved intact.

`STATUS_FINAL = EPISTEMOS_V0_6_PASS`.
