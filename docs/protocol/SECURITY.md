# EPCTX/1 — Security

**P0 invariants:** `PRIVATE_EPCTX_LEAK = 0`, `PRIVATE_EXPANSION_LEAK = 0`,
`CROSS_TENANT_EPCTX_LEAK = 0`.

The document is a projection over objects the retrieval already authorized; it never lowers a
boundary. Identity is server-side on every transport.

## Identity is never in the payload

| transport | identity source | payload cannot set |
|---|---|---|
| SDK Local | bound `Principal` | — |
| REST `POST /context` | bearer token → `Principal` | tenant / principal / capabilities / namespace |
| MCP `epistemos_context` | server principal | tenant / principal / capabilities |

A REST body or MCP args carrying `tenant`/`principal`/`capabilities` are ignored; only query shaping
(`query`, `intent`, `as_of`, `requested_budget`, `consumer_profile`) is read. Verified by
`test_rest_body_cannot_spoof_identity` and `test_mcp_args_cannot_spoof_identity`.

## Attacks covered (§28)

| attack | defense |
|---|---|
| principal / tenant / space / capability spoof | identity server-side; body/args carry no authority |
| cross-tenant read | retrieval firewalled by tenant; outsider's document is empty |
| private prior version / contradiction / provenance leak | only authorized objects are projected; attached contradictions re-authorized per principal |
| forged expansion handle | unknown → refused identically to unauthorized (no existence oracle) |
| cross-principal / cross-tenant handle | handle bound to minter's identity + tenant; mismatch → refused |
| stale / revoked handle | members re-authorized **live** at redemption; a since-revoked member is dropped (`STALE_EXPANSION_PRIVATE_LEAK = 0`) |
| oversized request | REST body capped (8 MB) → `400`; server stays up |
| deeply nested / malformed payload | rejected as a clean error, never a crash |
| unicode abuse / control chars | valid unicode is data; control chars/NUL cleanly rejected |
| prompt injection inside evidence | evidence is data; the renderer fences it and never executes it |

## Expansion handles

Opaque, carrying no ids. The private ids they stand for live in a per-engine server-side registry.
Redemption re-checks the presenting principal's fingerprint (tenant / agent / namespace) and re-runs
`is_readable` for every member at the bound snapshot. Capabilities are **not** baked in — authorization
is evaluated at redemption, so revocation takes effect immediately (ADR-042). Experimental until its
own hardening pass; off the stable path unless a consumer opts in.

## Non-goals

No cryptography is invented (§6). `context_hash` is a content digest for tamper detection, not a
signature. No new cache is added by this protocol; there is no shared cross-principal state.
