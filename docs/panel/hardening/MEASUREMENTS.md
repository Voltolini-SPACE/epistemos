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

## Performance (§15)

Read-model latency (in-process `PanelService`, median of 15 reps, ms), realistic mixed corpus
(~70% claims, evidence, sources, reviews):

| op | 100 | 1,000 | 10,000 |
|---|--:|--:|--:|
| counts | 0.78 | 8.3 | 96.7 |
| overview | 1.79 | 13.9 | 134.6 |
| graph | 0.82 | 8.2 | 85.9 |
| as_of | 0.52 | 5.6 | 52.0 |
| list_claims | 0.38 | 3.5 | 41.8 |
| search | 0.77 | 7.7 | 88.2 |
| claim_detail | 0.64 | 6.5 | 74.6 |
| activity | 0.65 | 2.6 | 2.4 |

**Optimization applied this mission.** The aggregate views (`counts`/`overview`/`graph`/`as_of`/
`agents`/`sources`) previously scanned the store **once per kind** (7 passes, 7× `json.loads` per
object). `_readable_by_kinds` does one bucketed pass. Measured at 10k objects:

| op | before | after | speedup |
|---|--:|--:|--:|
| counts | 317 ms | 97 ms | 3.3× |
| overview | 363 ms | 135 ms | 2.7× |
| graph | 298 ms | 86 ms | 3.5× |
| as_of | 274 ms | 52 ms | 5.3× |

Semantics are unchanged (same firewall, same objects), pinned by
`tests/panel/test_readmodel_perf_equiv.py`.

**Residual characteristic.** Everything except `activity` (bounded to 200 events) remains **O(N)** in
authorized-corpus size — the firewall must evaluate `is_readable` per object *before* any limit, so
an authorized count/graph cannot short-circuit. At ≤1k objects the panel is snappy (<15 ms); at 10k
the heaviest view is ~135 ms. Beyond ~10k, a per-principal authorized index (cached read-model)
would be the next step — flagged as future work, not a v1 blocker. Ledger tail
(`read_events(since_seq)`) is O(N) on `MemoryStore` and an indexed range scan on SQLite.
