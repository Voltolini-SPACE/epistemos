# Integration spec: Hermes

**Status: SPEC ONLY. Not integrated.** How Hermes *could* consume EPCTX/1 later. The EPISTEMOS core
imports nothing from Hermes.

## Contract

Hermes could request, via EPCTX/1 over SDK / REST / MCP:

- **memory / context** for a task (`engine.epctx(query, intent="current")`);
- **historical context** (`intent="historical"` or `as_of=<tx>`);
- **decision explanation** (`intent="decision"` — decisions with their evidence refs).

EPISTEMOS returns the document; Hermes decides how to use it. EPISTEMOS executes nothing on Hermes's
behalf and grants no capability.

## Boundary rules

- No Hermes import in the EPISTEMOS core; the adapter (if any) lives in Hermes.
- Identity server-side; Hermes presents a principal, never authority-in-payload.
- EPCTX/1 is unchanged by this consumer — Hermes reads the same document any agent reads.

## Why not yet

Prove the protocol is independent first (EPISTEMOS-09). Integration is a later, opt-in mission.
