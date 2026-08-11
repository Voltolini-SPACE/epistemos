# Generic MCP / Agent Adapter — Specification

## Purpose

Any agent or orchestrator (Claude, OpenAI, or another framework) can use EPISTEMOS as a sovereign
memory/context layer via the generic MCP server or the SDK/REST — with no lock-in.

## MCP tool surface (implemented in `src/epistemos/mcp/`)

A **fixed, narrow allow-list** (JSON-RPC 2.0): `assert_fact`, `current`, `search`, `timeline`,
`explain`, `record_decision`, `health`. Each maps to a validated Engine call. Deliberately **absent**:
`execute`, `eval`, `query_raw_sql`, `query_raw_cypher`, `filesystem_read`, `url_fetch`, `shell`.

## Security contract (hostile boundary)

- **Server-side identity.** The connected client's `Principal` is set when the server starts; tool
  arguments cannot change tenant/namespace (no scope escalation).
- **Arguments are data.** Injection/prompt payloads are stored inertly and never executed.
- **Errors are tool errors**, not crashes: domain failures return `isError:true`; unknown tools/methods
  are JSON-RPC errors (`-32602`/`-32601`).
- **Recall is data, not instructions.** A consuming agent MUST treat returned context as untrusted
  data when feeding it to a model.

## Portability

The same knowledge is reachable via `LocalClient` (SDK), `RemoteClient` (REST), or MCP, and is fully
exportable (`export`) in a versioned JSON format (ADR-014) — EPISTEMOS is not a data prison and any
agent binding is swappable.
