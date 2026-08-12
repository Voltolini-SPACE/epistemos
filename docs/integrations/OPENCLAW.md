# Integration spec: OpenClaw

**Status: SPEC ONLY. Not integrated.** How OpenClaw *could* consume EPCTX/1 later. The EPISTEMOS core
imports nothing from OpenClaw.

## Contract

OpenClaw could consume EPCTX/1 through any of the three transports, unchanged:

- **SDK** — in-process `LocalContextClient`;
- **REST** — `POST /context` with a bearer token;
- **MCP** — the `epistemos_context` tool.

The document semantics are identical across transports (transport parity is a freeze gate). OpenClaw
decides how to reason and what to attempt; EPISTEMOS returns context and executes nothing.

## Boundary rules

- No OpenClaw dependency in the EPISTEMOS core.
- Identity server-side (token / server principal); no authority in the request payload.
- EPCTX/1 stays the same regardless of which OpenClaw component consumes it.

## Why not yet

EPISTEMOS-09 establishes the independent protocol; a real OpenClaw integration is a separate mission.
