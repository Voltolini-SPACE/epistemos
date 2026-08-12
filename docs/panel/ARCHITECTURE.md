# Panel architecture

The EPISTEMOS Panel is the official operational interface — a **local-first, zero-egress** window into
a live Engine. It is a *consumer*, not an authority (ADR-030).

```
EPISTEMOS CORE            epistemos.core.Engine — the ONLY authority
  (ledger, spaces          bitemporal knowledge + claim graph + spaces firewall
   firewall, belief)              │  authorized primitives only
                                  ▼
API / EVENT BOUNDARY       epistemos.api.panel   — authorized read-model (views)
  (trusted, server-side)   epistemos.api.stream  — authorized SSE tail (§34)
                           epistemos.api.server  — stdlib HTTP+SSE, StaticTokenAuth, strict CSP
                                  │  JSON + text/event-stream, already authorized, per-principal
                                  ▼
EPISTEMOS PANEL            src/epistemos/panel/web/*  — vanilla HTML/CSS/JS (untrusted browser)
  (consumer)               grants nothing; renders only what the API returns
```

## Layers

- **Core** — untouched by the panel except one additive public method, `Engine.is_readable(principal,
  obj)`, a thin wrapper over the existing `_can_read` (`IDENTITY→TENANT→SPACE→CAPABILITY→POLICY`,
  fail-closed). It is the single predicate the whole boundary gates on.
- **Boundary** (`epistemos.api`) — trusted server-side code that turns authorized primitives into
  views: `PanelService` (listings, counts, knowledge graph, claim/evidence/belief/explain, timeline,
  bitemporal `as_of`, spaces/agents/sources/health) and `authorized_events` (the redacted, filtered
  ledger tail behind both SSE and the activity feed). The invariant, enforced by tests: **no object or
  event is serialized to a response without passing `is_readable`**.
- **Panel** (`web/`) — a vanilla ES-module SPA (`app.js` shell/router/palette, `api.js` client + SSE,
  `graph.js` canvas explorer, `screens.js` views, `charts.js`/`dom.js` helpers). No framework, no npm,
  no CDN. Served as static files by the same server under a strict self-only CSP.

## What the browser never decides

tenant · capabilities · visibility · acceptance · promotion · reviewer identity · truth/belief. Identity
comes only from the session token (resolved to a `Principal` server-side); a query or body can never
choose scope. The panel v1 is **read-only** — there is no mutating route, so it grants no authority.

## Data flow

A screen calls an `/api/*` endpoint → the server resolves the `Principal` from the cookie/bearer →
`PanelService` assembles the view from candidates filtered through `is_readable` → JSON. Live changes
arrive over `/api/stream` (SSE): the server tails the ledger, drops anything the principal cannot read,
and emits redacted envelopes; the browser updates counters, the activity feed, and (debounced) the
graph so genuinely-new nodes pulse in. See `REALTIME.md`, `SECURITY.md`.
