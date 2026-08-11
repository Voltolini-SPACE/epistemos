# Adapters

Adapters depend on EPISTEMOS; **the core depends on none of them** (`CORE ← ADAPTER`, ADR-013).

Nothing here is implemented in the EPISTEMOS-01 mission — integration with NOMOS / Hermes / OpenClaw
is **forbidden** in this mission. These directories hold *contracts and future homes* only:

- `nomos/` — see [`docs/integration/NOMOS_ADAPTER_SPEC.md`](../docs/integration/NOMOS_ADAPTER_SPEC.md)
  (EPISTEMOS never grants capabilities; NOMOS decides).
- `hermes/` — see [`docs/integration/HERMES_ADAPTER_SPEC.md`](../docs/integration/HERMES_ADAPTER_SPEC.md).
- `openclaw/` — see [`docs/integration/OPENCLAW_ADAPTER_SPEC.md`](../docs/integration/OPENCLAW_ADAPTER_SPEC.md).
- `generic/` — see [`docs/integration/GENERIC_MCP_SPEC.md`](../docs/integration/GENERIC_MCP_SPEC.md);
  the generic MCP server itself is implemented in `src/epistemos/mcp/`.
