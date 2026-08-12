# ADR-031 — Real-time event boundary: Server-Sent Events over the ledger

**Status:** Accepted (panel-v1)

## Context

"See the knowledge thinking" (§3–§8) needs the panel to reflect real changes — claims, evidence,
reviews, contradictions, decisions, acceptances — **without a full reload**, with an honest connection
state (LIVE / RECONNECTING / OFFLINE / STALE) and automatic reconnection. The core already has the
perfect event source: the **append-only, hash-chained ledger**, monotonically sequenced by `seq`. The
question is the transport, and it must not add infrastructure (§7) or a dependency.

## Decision

Use **Server-Sent Events (SSE)** — `text/event-stream` on the existing stdlib `http.server`.

- **Why SSE over WebSocket:** the panel's realtime need is **one-directional** (server → browser
  notifications); the panel issues no mutations, so a bidirectional socket buys nothing. SSE is plain
  HTTP (works through the same server, same auth header path, same localhost bind), the browser's
  `EventSource` gives **automatic reconnection for free**, and resuming is built in via `Last-Event-ID`.
  WebSocket would need a framing/upgrade implementation on top of stdlib and a hand-rolled reconnect —
  more code, more surface, no benefit here.
- **The ledger `seq` is the SSE event `id`.** On reconnect the browser sends `Last-Event-ID: <seq>`; the
  server resumes tailing from `since_seq = seq`, so no authorized event is missed or duplicated across a
  reconnect. Ordering is the ledger's total order.
- **The stream is a tail, not a firehose.** Each connection polls `store.read_events(since_seq)` on a
  short interval, emits the authorized, redacted envelopes (ADR-032), and advances `since_seq`. A
  heartbeat comment (`: keep-alive`) is sent when idle so proxies and the browser can detect liveness;
  the panel flips to STALE if no event/heartbeat arrives within a bound, and to OFFLINE on transport
  error (then `EventSource` auto-reconnects).
- **No fake realtime (§36).** There is no `setInterval` inventing events, no random metrics, no
  simulated growth. If nothing happens in the ledger, the stream is quiet (only heartbeats). Every
  event corresponds to a real ledger record.

## Consequences

- Realtime works on pure stdlib, offline, with zero added dependencies, and survives disconnects with
  exact resume semantics.
- Back-pressure is naturally bounded: a slow client just tails from its last `seq`; the server holds no
  per-client buffer beyond the current poll batch.
- The same authorized-tail primitive powers both the live SSE stream and the initial Activity feed
  (a bounded historical tail), so there is one code path to secure.

## Rejected alternatives

- **WebSocket** — rejected: bidirectional transport for a one-directional need; more stdlib code, manual
  reconnect, no gain.
- **Long-polling / periodic full refetch** — rejected: higher latency, wasteful, and tempts "poll the
  whole store" which risks leaking counts; the incremental `seq` tail is cheaper and safer.
- **Client subscribes to a raw ledger feed** — rejected on security grounds (ADR-032): the browser must
  never receive unauthorized events to filter locally.
