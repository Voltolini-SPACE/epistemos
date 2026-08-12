# Integration spec: NOMOS

**Status: SPEC ONLY. Not integrated.** This describes how NOMOS *could* consume EPCTX/1 in a future
mission. Nothing here is built, and the EPISTEMOS core imports nothing from NOMOS.

## Contract

```
NOMOS ──(authorized request, NOMOS-issued principal)──▶ EPISTEMOS
EPISTEMOS ──(EPCTX/1)──▶ NOMOS / agent
NOMOS ──(action decision, via its own policy)──▶ effect
```

- NOMOS is the control / authorization plane; EPISTEMOS is the knowledge plane.
- EPISTEMOS returns context; **EPISTEMOS never grants a capability and never executes an action.**
- NOMOS decides what is allowed and what to attempt, using EPCTX's explicit contradictions,
  completeness, provenance, and temporal state as inputs to that decision.

## Boundary rules

- The core dependency direction stays `CORE ← ADAPTER`, never `CORE → NOMOS`.
- Identity is server-side: NOMOS presents a principal/token to EPISTEMOS; it does not smuggle
  authority in an EPCTX request body.
- Any NOMOS-side adapter lives in NOMOS, not in the EPISTEMOS core.

## Why not yet

EPISTEMOS-09 proves EPCTX is a genuinely independent protocol first. Integration is a separate,
opt-in mission with its own gates.
