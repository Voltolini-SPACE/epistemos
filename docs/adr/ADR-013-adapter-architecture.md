# ADR-013 — Adapter architecture: CORE ← ADAPTER, never the reverse

**Status:** Accepted (v0.1)

## Context
EPISTEMOS must integrate later with NOMOS, Hermes, and OpenClaw **without** becoming a mandatory
dependency of any of them, and without any of them becoming a dependency of the core (mission §21).
Integration is **forbidden in this mission** — only contracts are produced.

## Decision
The dependency direction is strictly **`CORE ← ADAPTER`**. Adapters depend on EPISTEMOS; the core
imports nothing from any external system. Adapters live under `adapters/{nomos,hermes,openclaw,
generic}/` and are specified (not implemented) in `docs/integration/`:
- **NOMOS adapter** — EPISTEMOS provides context/facts/history/evidence/precedent; **NOMOS decides**.
  **EPISTEMOS never grants a capability.**
- **Hermes / OpenClaw adapters** — consume memory/context via SDK/REST/governed-MCP; EPISTEMOS stays
  **substitutable and removable** without breaking those systems (loose coupling, mission §45).

## Consequences
- EPISTEMOS can run standalone or alongside any agent; removing it does not break the others.
- Each future integration gets its own mission and gate (EPISTEMOS-NOMOS-01, etc.).

## Rejected alternatives
- **Core importing NOMOS/Hermes/OpenClaw**: couples the sovereign engine to them; rejected.
- **EPISTEMOS as PDP / capability grantor**: out of scope; it informs, NOMOS decides.
