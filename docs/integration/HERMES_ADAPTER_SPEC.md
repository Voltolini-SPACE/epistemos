# Hermes Adapter — Specification (contract only; NOT implemented in EPISTEMOS-01)

## Purpose

Let Hermes use EPISTEMOS as its **persistent memory / context** layer: persistent memory, agent
history, entity knowledge, episodic history, and tool-invocation history — while EPISTEMOS remains
**substitutable** (Hermes must keep working if EPISTEMOS is swapped out or removed).

## What Hermes gets

- `assert_fact` / `observe` / `remember` to record knowledge and episodes with provenance.
- `current` / `as_of` / `timeline` for bitemporal recall ("what do we know now / knew at T").
- `search` (explainable) and `explain` for grounded, auditable context.
- `record_decision` + `explain(decision)` for decision lineage across sessions.

## Boundaries

- Access via **SDK (local)** or **REST/governed-MCP (remote)** — Hermes is a *client*, never imported
  by the core (`CORE ← ADAPTER`).
- Identity: Hermes presents a `Principal` (tenant/agent/namespace); per-agent private memory uses a
  per-agent namespace. EPISTEMOS enforces isolation fail-closed.
- All recalled content is **data**, not instructions — Hermes must re-assert that boundary when it
  feeds recalled context into a model (mission threat model S1/S2/S36).

## Out of scope for EPISTEMOS-01

No Hermes integration code, no shared runtime. Future `EPISTEMOS-HERMES-01` mission, own gate.
Hermes remains **READ-ONLY / untouched** in this mission.
