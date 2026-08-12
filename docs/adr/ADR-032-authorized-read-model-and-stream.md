# ADR-032 — Authorized read-model & server-side stream filtering

**Status:** Accepted (panel-v1)

## Context

The panel needs listings (claims, evidence, reviews, facts, sources, decisions, spaces, agents), a
knowledge **graph** (nodes + typed edges), aggregate **metrics**, a **timeline** with bitemporal
time-travel, and a live **event stream**. Every one of these is a *derived view* over many objects —
exactly where a leak hides: a count, a rank, a graph edge to a hidden node, an error that distinguishes
absent from forbidden, or a raw ledger payload pushed to the browser. The P0 invariants are absolute:

```
PRIVATE_UI_LEAK = PRIVATE_GRAPH_LEAK = PRIVATE_SEARCH_LEAK = PRIVATE_STREAM_LEAK = 0
```

## Decision

All views are assembled in a trusted server-side **read-model** (`epistemos.api.panel`) and an
**authorized stream** (`epistemos.api.stream`), both built on one rule: **candidate → authorize →
project**. Nothing is emitted that `Engine.is_readable(principal, obj)` does not pass.

- **Authorized enumeration.** `list_readable(kinds, …)` takes candidates from the store, filters each
  through `is_readable` **before** any limit/sort/count, then projects a **redacted** shape (id, kind,
  and only fields the object model already exposes to a reader). Limit is applied *after* the firewall,
  so a page size never leaks the existence of hidden objects. Counts are counts *of authorized objects*.
- **Graph is assembled from authorized objects only.** A node exists in the graph iff the caller can
  read it; an edge exists iff **both endpoints** are readable. A `CONTRADICTS`/`SUPPORTS` edge to a
  private claim/evidence is dropped whole — the graph never renders a placeholder or a dangling stub
  that betrays a hidden neighbor (`PRIVATE_GRAPH_LEAK = 0`). Expansion ("expand neighbors") re-runs the
  same filter; there is no privileged expansion path.
- **Belief/explain are passthrough to the core.** `explain_claim`/`explain` already elide unreadable
  evidence, reviews, source and genealogy (the v0.4/v0.5 guarantee); the panel renders exactly what the
  core returns and never back-fills.
- **The stream is filtered at the source (§34).** For each new ledger record the stream: (1) drops it
  unless `record.tenant == principal.tenant` (cross-tenant first, cheapest, absolute); (2) resolves the
  object the event concerns (from the payload's id or the current projection); (3) emits **only** if
  `is_readable` passes; (4) emits a **redacted envelope** — `{seq, op, ts, kind, id, actor, summary}` —
  **never the raw payload**. A private claim's assertion, a private evidence attachment, a review in a
  space you're not in: none reach the browser at all. There is no client-side filtering.
- **No existence oracle.** Reads of a specific out-of-scope id return the same "not found" as a truly
  absent id (the core's `NotFoundError`/`None` contract), and error bodies never distinguish
  "forbidden" from "absent" for cross-scope ids. Metrics/graph/stream never reveal a hidden object's
  existence through a delta.
- **Time-travel stays authorized.** `as_of`/timeline run through the same firewall at the queried
  transaction/valid time; viewing the past never exposes an object the caller could not read then or now
  (authorization is evaluated against the live grant state, fail-closed).

## Consequences

- The entire UI attack surface for a private-data leak reduces to one predicate (`is_readable`) applied
  uniformly across list/graph/search/timeline/stream — which is exhaustively adversarially tested.
- The boundary may read `store.objects`/`store.read_events` directly (it is trusted server code), but it
  is an invariant, enforced by tests, that **no object or event is serialized to a response without
  passing `is_readable`**.
- Redaction is defensive-in-depth: even an authorized event carries only a summary, so a future bug that
  widened authorization could not also dump a raw private payload.

## Rejected alternatives

- **Send everything, hide in CSS/JS** — rejected: the data is already in the browser; "hidden" is a lie.
- **Trust a client-supplied filter (tenant/space in the query)** — rejected: the browser never chooses
  scope; scope comes from the token's `Principal` only.
- **Filter after ranking/limiting** — rejected: leaks counts and existence; the firewall is
  candidate-boundary-first, matching ADR-026.
