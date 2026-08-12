# Panel security

The browser is an **untrusted boundary**. The panel's security model is one sentence: *nothing an
unauthorized principal cannot read is ever placed in a response* — not in a listing, a count, a graph
node/edge, a search hit, a timeline, an event, or an error. The P0 invariants:

```
PRIVATE_UI_LEAK = PRIVATE_GRAPH_LEAK = PRIVATE_SEARCH_LEAK = PRIVATE_STREAM_LEAK = 0
```

## How it holds

- **One authorization predicate.** Every listing, graph node, metric, timeline entry, search hit and
  stream event is gated by `Engine.is_readable(principal, obj)` — the same fail-closed read decision
  the core uses. The boundary never re-implements authorization, so the UI cannot widen it.
- **Candidate → authorize → project.** The firewall runs **before** any limit/sort/count, so a page
  size or a counter never reveals a hidden object. Counts are counts *of authorized objects*.
- **Graph edges need both endpoints.** A node appears iff readable; an edge appears iff **both** ends
  are readable. An edge to a private neighbour is dropped whole — no dangling stub (§ visibility
  composition). Expansion re-runs the same filter; there is no privileged path.
- **The stream is filtered at the source (§34).** For each ledger record: drop unless it is in the
  caller's tenant *and* namespace; resolve the object it concerns; emit only if readable; emit a
  **redacted envelope** (`seq, op, kind, ts, actor, object, object_kind, summary`) — never the raw
  payload. The browser cannot filter what it never receives.
- **No existence oracle.** A specific out-of-scope id returns the same `NotFound`/`None` as a truly
  absent id, and error bodies for 401/403/404 never distinguish forbidden from absent.
- **Identity is server-side only.** The bearer token (or the `eps_session` HttpOnly, SameSite=Strict
  cookie set by `POST /api/session`) resolves to a `Principal` server-side. A query/body cannot choose
  tenant, capability, or visibility. Tokens never appear in URLs (§35).
- **Zero-egress at the browser.** A strict `Content-Security-Policy` (`default-src 'self'`, no external
  origin, no wildcard) blocks any fetch/font/script/image/beacon to another host. The page is fully
  self-contained.
- **Read-only.** No mutating route exists, so the UI grants no authority (acceptance/promotion/review
  all remain core-side capabilities, absent from the panel).

## Client storage (§35)

The panel persists **no** knowledge in `localStorage`/`IndexedDB`/cache/service-worker. The only client
state is the HttpOnly session cookie (not JS-readable) and, optionally, non-sensitive UI preferences.
`Cache-Control: no-store` is set on API and static responses.

## Attack coverage (tests/panel/)

tenant/space/principal/capability spoof · hidden-node retrieval · graph-expansion leak · search-count
leak · timeline leak · event-stream leak · explain-traversal leak · private-evidence leak (visibility
composition) · error oracle · cross-tenant. **22 automated tests**, including a real ephemeral server
proving CSP, no-oracle errors, and private-leak=0 over the wire. The boundary reuses the core's
firewall, itself covered by the core mutation harness (39/39 killed).
