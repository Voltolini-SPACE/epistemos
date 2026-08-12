# ADR-030 — Panel architecture: the UI is a consumer, authority stays in the core

**Status:** Accepted (panel-v1)

## Context

EPISTEMOS-PANEL-01 builds the official operational interface. The mission's non-negotiables:
*authorization before visualization*, *private data never reaches unauthorized UI*, *the core remains
the source of truth*, *the UI never grants authority*, and *local-first / zero-egress*. The browser is
an **untrusted boundary** (§33): it must never decide tenant, capabilities, visibility, acceptance,
promotion, reviewer identity, or truth/belief.

The core (`epistemos` v0.5.0) is a pure-stdlib Python library with **zero runtime dependencies**. A
thin stdlib REST adapter already exists (`epistemos.api.rest`, `http.server` + `StaticTokenAuth`
resolving a bearer token → `Principal` **server-side**).

## Decision

Three layers, strictly separated:

```
EPISTEMOS CORE  (Engine, ledger, spaces firewall — the ONLY authority)
      │  authorized primitives only
      ▼
API / EVENT BOUNDARY  (epistemos.api.panel + .stream + .server — trusted server-side)
      │  JSON + text/event-stream, per-principal, already authorized
      ▼
EPISTEMOS PANEL  (vanilla HTML/CSS/JS in the browser — untrusted consumer)
```

- **Stack: stdlib server + vanilla JS.** No framework, no npm, no CDN, no build step — the only stack
  consistent with zero-egress, local-first, and the core's zero-dependency posture. The graph, charts,
  and force layout are hand-written on Canvas/SVG; no d3/three/react is fetched. The panel is served as
  static files by the same stdlib server, so it runs fully offline from a single `python -m
  epistemos.panel`.
- **Authority never leaves the core.** The boundary calls only *authorized* Engine primitives. The one
  new core method is `Engine.is_readable(principal, obj)` — a public wrapper over the existing
  `_can_read` (`IDENTITY→TENANT→SPACE→CAPABILITY→POLICY`, fail-closed). Every listing, graph node,
  search hit, timeline entry, and stream event the boundary emits is gated by it.
- **The browser sends only its bearer token.** The token resolves to a `Principal` server-side
  (`StaticTokenAuth`); a request body/query can never choose tenant, capability, or visibility. Any
  mutable action (accept/promote/review) would go through the same capability enforcement in the core —
  the panel v1 is **read-only** and issues no mutations, so it can grant nothing by construction.
- **The panel replicates no epistemological rule.** Belief is not recomputed in JS; it is rendered from
  `explain_claim`/`belief`. Visibility is not evaluated in JS; unreadable objects never arrive. The UI
  is a projection of authorized state, never a second authority.

## Consequences

- A compromised or malicious browser cannot read anything its token could not already read via the API;
  the attack surface for a UI leak is the boundary's authorization filter, which is unit-tested to
  `PRIVATE_*_LEAK = 0`.
- The panel is deployable as a local app (`localhost`, no cloud required, §47) and is **distinct** from
  the marketing page at `voltolini.space/epistemos`.
- Adding a framework later is possible but would be a supply-chain and egress regression; the vanilla
  choice is deliberate, not a limitation.

## Rejected alternatives

- **React/Next/Vite SPA** — rejected: needs npm + a build toolchain + (usually) CDN fonts/assets;
  violates zero-egress/zero-dep and adds a supply chain the core deliberately avoids.
- **Browser filters private data** — rejected outright (see ADR-032): private objects must never be
  sent to the browser to be hidden later.
- **Static export of a snapshot** — rejected: the mission requires *real, live* data, not a build-time
  dump.
