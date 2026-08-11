# ADR-012 — External APIs: thin adapters, no implicit authority

**Status:** Accepted (v0.1)

## Context
EPISTEMOS needs a Python SDK, a REST API, and an MCP server (mission §20). None may contain domain
logic or hold implicit authority, and MCP must be treated as hostile.

## Decision
All external interfaces are **thin adapters over the Engine**, built on the **standard library** (no
web framework dependency):
- **Python SDK** (`sdk.py`): `LocalClient` (Engine direct) and `RemoteClient` (REST over
  `http.client`) with identical method names and **identical error semantics** (HTTP codes mapped
  back to `epistemos.errors` types). The SDK duplicates no rules.
- **REST** (`api/rest.py`): `http.server`; binds **`127.0.0.1` by default** (never `0.0.0.0`
  implicitly); **pluggable `AuthResolver`** (default static bearer-token map); **identity comes from
  the token, not the request body**; Engine exceptions → HTTP status.
- **MCP** (`mcp/`): JSON-RPC 2.0; a **fixed, narrow tool allow-list** (no `execute`/`eval`/raw-SQL/
  raw-Cypher/`filesystem_read`/`url_fetch`); **server-side identity** so a client cannot escalate
  tenant; transport-independent `handle()` for testability + `serve_stdio()`.

## Consequences
- One place (the Engine) enforces all invariants; adapters can be added/replaced freely.
- Zero web-framework supply chain; localhost-only default posture.

## Rejected alternatives
- **FastAPI/Flask**: third-party runtime dependency; unnecessary for a thin adapter; rejected.
- **Generic MCP tools (raw query/exec)**: injection/authority risk; rejected.
- **Client-supplied tenant in requests**: scope escalation; rejected (identity is server-side).
