# NOMOS Adapter — Specification (contract only; NOT implemented in EPISTEMOS-01)

> **EPISTEMOS NEVER GRANTS CAPABILITIES.** NOMOS is the authority; EPISTEMOS provides knowledge.

## Roles

- **NOMOS** = control plane / policy authority (Policy Decision Point). Decides *what an agent may do*.
- **EPISTEMOS** = knowledge plane. Records *what the system knows, how, when, and from where*.

## Contract flow

```
NOMOS ──(1) authorized context request (tenant, principal, agent, namespace, question)──▶ EPISTEMOS
EPISTEMOS ──(2) context / evidence / precedent / decision-records / temporal state──────▶ NOMOS
NOMOS ──(3) PDP decision (allow/deny/attenuate) using that evidence──────────────────────▶ AGENT
```

EPISTEMOS answers only within the scope of the `Principal` NOMOS presents. It returns **facts,
precedent, history, context, decision records, and evidence** — never a permission, capability, or
authorization verdict.

## Dependency direction

`CORE ← ADAPTER`. The adapter (`adapters/nomos/`) depends on EPISTEMOS (SDK/REST/governed-MCP).
EPISTEMOS core imports nothing from NOMOS. Removing EPISTEMOS must not break NOMOS (loose coupling).

## Capability-readiness (future, not this mission)

`Principal.capabilities` is the seam for NOMOS to **attenuate** what a principal may do inside
EPISTEMOS (e.g. read-only context for a low-trust agent). NOMOS *reduces* capabilities; EPISTEMOS
enforces the reduced set fail-closed. EPISTEMOS still never *adds* a capability.

## Explicitly out of scope for EPISTEMOS-01

No code that talks to NOMOS; no shared process; no capability grant path. This document is the
contract for a future `EPISTEMOS-NOMOS-01` mission with its own gate.
