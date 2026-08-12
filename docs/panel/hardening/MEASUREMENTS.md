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

## Soak (§16)

Duration executed: **90 s** (recorded honestly; not a multi-hour run). Load: 1 writer (~20 obj/s),
2 HTTP readers, 2 SSE clients on **controlled reconnect** every 7 s / 11 s.

| Metric | start | end | verdict |
|---|--:|--:|---|
| threads | 9 | 11 | bounded (SSE reconnects do not leak) |
| file descriptors | 10 | 14 | bounded (fluctuates with reconnects, no leak) |
| RSS | 32 MB | 56 MB | grows with the **corpus** (0→2,918 objects), not a leak |

No thread/fd leak across ~15 SSE reconnect cycles. RSS growth is attributable to real data (the
writer added 2,918 objects); it is not unbounded per-request growth.

## Accessibility (§13) — automated DOM sweep

CSP (`script-src 'self'`) correctly blocks injecting an external axe-core bundle, so the audit is a
self-authored WCAG-AA DOM sweep (no runtime dependency added). Across overview/graph/claims/timeline/
spaces/agents/sources/health:

- **Structural: 0 issues** — one `<main>` + `<nav>` landmark, exactly one `<h1>` per screen, no
  skipped heading levels, every `<img>` has alt, every control has an accessible name.
- **Contrast: 0 issues** over 478 checked text elements (WCAG AA 4.5:1 / 3:1). Raised `--fg-3`
  (#6E7488 → #868DA3) and the retracted badge to clear 4.5:1.
- **Dialogs:** command palette and inspector are `role="dialog"` with labels; palette input labeled.
- **Live regions:** connection indicator `role="status"`; activity feed `role="log"` + `aria-live="polite"`.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` collapses all animation/transition.
- **Fixes this mission:** graph screen gained an accessible `<h1>`; timeline date input gained an
  `aria-label`; overview/spaces section headings promoted to `<h2>` (no level skip).

*Caveat:* a manual screen-reader pass (VoiceOver/NVDA) is still recommended — automation covers
structure/contrast/roles, not the full lived SR experience.

## Responsive (§14)

Horizontal-overflow check across **320 / 375 / 430 / 768 / 1024 / 1440 / 1920** (every breakpoint
regime: <720 mobile, 720–1000 tablet, >1000 desktop):

- **0 horizontal overflow** on any screen after fixes.
- **Fixes this mission:** activity-feed summary (`.ev .s`) needed `min-width:0` to truncate instead
  of overflow; the `.topbar` and `.main` grid items needed `min-width:0` so a 320 px topbar shrinks
  below its content instead of pushing a 358 px scroll width.
- Mobile (<720) collapses the sidebar to a bottom-nav; cards stack single-column. Verified at 320 px.
