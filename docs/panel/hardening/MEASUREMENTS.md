# EPISTEMOS Panel — Hardening Measurements (EPISTEMOS-PANEL-HARDENING-01)

Reference host: Apple Silicon macOS, CPython 3.14.5, `MemoryStore`. Numbers are from the adversarial
harnesses in the mission log; the fast deterministic subsets are pinned as tests under `tests/panel/`.

## SSE / realtime (§7)

Harness: raw-socket SSE client vs a live writer. Poll interval `_STREAM_POLL_SECONDS = 1.0`,
heartbeat `15s`.

| Metric | Result |
|---|---|
| `EVENT_LOSS` | **0** (41/41 authorized events delivered) |
| `DUPLICATE_RATE` | **0** |
| `ORDERING` | strictly monotonic by ledger `seq` |
| Reconnect resume (`Last-Event-ID`) | `RESUME_LOSS=0`, `RESUME_REDELIVERED_OLD=0` |
| Reconnect socket setup | ~1 ms (event latency bounded by the 1 s poll) |
| Malformed `Last-Event-ID` | HTTP 200, falls back to seq 0, no crash |
| 4 concurrent clients | identical delivered set (71/71 each) |

Delivery latency is bounded by the poll interval (≤ ~1 s), a deliberate low-CPU design (no per-write
fan-out). Regression: `tests/panel/test_sse_realtime.py`.

## Concurrency / race (§8)

Harness: 1 writer thread ingesting claims/evidence/reviews into the same Engine while 12 reader
threads hammer every surface over HTTP, 30 rounds (360 reader batches, ≈5.8k HTTP reads).

| Metric | Result |
|---|---|
| HTTP 500 under load | **0** |
| Torn counts (`knowledge_objects != Σ kinds`) | **0** |
| Private leak to an unauthorized reader mid-write | **0** |

Root cause of safety: `MemoryStore` serializes every op under an `RLock` and snapshots
`objects()`/`read_events()` under the lock; SQLite serializes under a connection lock. Panel reads
are therefore consistent under `ThreadingHTTPServer`. Regression: `tests/panel/test_concurrency.py`.

## Performance characteristic (feeds §15)

`/api/graph`, `/api/counts`, `/api/overview` enumerate **all** authorized objects (`is_readable` per
object) → **O(N)** in corpus size, then cap the graph at 1500 nodes. This is the dominant cost for
large corpora and the main input to the performance gate. Ledger tail (`read_events(since_seq)`) is
O(N) on `MemoryStore` (full-list filter) and an indexed range scan on SQLite.
