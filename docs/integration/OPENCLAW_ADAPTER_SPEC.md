# OpenClaw Adapter — Specification (contract only; NOT implemented in EPISTEMOS-01)

## Purpose

Let OpenClaw access EPISTEMOS knowledge/memory via **SDK**, **REST**, or a **governed MCP** server —
without modifying OpenClaw and without EPISTEMOS depending on it.

## Access modes

| Mode | How | Notes |
|------|-----|-------|
| SDK | `LocalClient` in-process | when co-located; direct Engine, shared error semantics |
| REST | `RemoteClient` over localhost | token auth; identity from token, not body |
| MCP | governed MCP server | hostile-boundary; fixed safe tool allow-list; server-side identity |

## Governed MCP posture

If exposed to OpenClaw over MCP, EPISTEMOS uses the `mcp/` server: **no** generic
`execute`/`eval`/raw-SQL/raw-Cypher/`filesystem_read`/`url_fetch` tools; only the narrow, validated
knowledge operations. A client cannot choose its tenant/namespace (server-side identity), and all
tool arguments are inert data.

## Boundaries

- `CORE ← ADAPTER`: adapter depends on EPISTEMOS; core imports nothing from OpenClaw.
- EPISTEMOS is removable without breaking OpenClaw's fundamental function (loose coupling, §45).

## Out of scope for EPISTEMOS-01

No OpenClaw changes, no integration code (mission §24 asks only for this spec). OpenClaw remains
**READ-ONLY / untouched**. Future `EPISTEMOS-OPENCLAW-01` mission, own gate.
