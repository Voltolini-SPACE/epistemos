# Real-time

The panel reflects real ledger changes without a reload, over **Server-Sent Events** (ADR-031). There
is no fake realtime: every event corresponds to a real, hash-chained ledger record — no `setInterval`
inventing activity, no random metrics, no simulated growth (§36).

## Transport

`GET /api/stream` → `text/event-stream`. The server tails `store.read_events(since_seq)` on a short
interval, emits the **authorized, redacted** envelopes (`SECURITY.md`, §34), and heartbeats (`: keep-
alive`) when idle. The ledger `seq` is the SSE event `id`, so on reconnect the browser's `EventSource`
sends `Last-Event-ID` and the server resumes exactly where it left off — no missed or duplicated
events.

## Client (`web/api.js` `Stream`)

`EventSource` carries the session cookie same-origin (no token in the URL). Connection state is honest:

| state | meaning |
|-------|---------|
| **LIVE** | connected, events/heartbeats arriving |
| **RECONNECTING** | transient error; `EventSource` auto-reconnects (resumes by seq) |
| **OFFLINE** | transport down / `navigator.onLine === false` |
| **STALE** | connected but no event/heartbeat within the staleness window — old data is **not** shown as live |

## What updates live

On each event the panel: prepends it to the visible activity feed (with a meaningful entrance),
refreshes the authorized counters, and — on the graph — debounces a reload with position preservation
so genuinely-new nodes **pulse in** while existing ones stay put. Metrics carry a per-value data-state
(LIVE/SNAPSHOT/STALE/UNAVAILABLE) and never invent a zero.

## Demo

`python -m epistemos.panel --demo --live-demo` runs a slow generator that appends **real** objects
through the Engine API (labeled to the `demo-feed` agent), so the stream shows genuine ledger activity
for demonstration — the realtime pipeline itself is always real.
