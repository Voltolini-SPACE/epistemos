# EPISTEMOS v0.3 — Final Benchmark

**Machine:** Apple Silicon, 10 cores. **Python:** 3.14.5. **Backend:** SQLite (WAL,
`synchronous=FULL`). **Harness:** `benchmarks/compare_retrieval.py` and the EPISTEMOS-03 capacity
census (`tools/`-free, in `scratchpad`). All numbers are measured on the v0.3 branch HEAD and
cross-checked against the frozen `epistemos-v0.2.0` tag for the before/after rows.

This report also **corrects the drifted v0.2 benchmark docs** (audit findings OV-05/OV-06): the
numbers below are what the shipped code produces on this machine today, with honest disk and
write-throughput costs.

## Headline: `explain()` is no longer O(ledger)

The v0.2 `explain()` scanned the whole ledger per genealogy node; v0.3 keys it through the
provenance index (ADR-022). Measured p50:

| ledger events | v0.2.0 `explain()` | v0.3 `explain()` | speedup |
|---|---|---|---|
| 1 000 | 14.5 ms | 0.057 ms | **254×** |
| 10 000 | 158.1 ms | 0.052 ms | **3 040×** |
| 100 000 | 1 926.4 ms | 0.057 ms | **33 800×** |

`explain()` is now **flat** in ledger size (proportional only to the genealogy actually walked).

## Retrieval at scale (`compare_retrieval.py`, text search p50)

| scale | legacy scan | v0.3 indexed | speedup |
|---|---|---|---|
| 1 000 | 47.7 ms | 0.26 ms | 183× |
| 10 000 | 425.0 ms | 2.23 ms | 190× |
| 100 000 | 4 738.4 ms | 28.0 ms | 169× |

(The scan is the correctness reference and the safe fallback; the index serves the hot path.)

## Capacity census (v0.3, SQLite, p50 unless noted)

| operation | 1k | 10k | 100k |
|---|---|---|---|
| `search` (common term) | 2.82 ms | 14.1 ms | 33.7 ms |
| `search` (rare term) | 0.058 ms | 0.061 ms | 0.059 ms |
| `current` | 0.025 ms | 0.025 ms | 0.025 ms |
| `as_of` | 0.016 ms | 0.016 ms | 0.016 ms |
| `timeline` | 0.009 ms | 0.013 ms | 0.097 ms |
| `explain` | 0.057 ms | 0.052 ms | 0.057 ms |
| `verify_integrity` | 0.018 s | 0.191 s | 2.05 s |
| `rebuild_projection` | 0.043 s | 0.484 s | 7.0 s |
| `export` | 0.008 s | 0.105 s | 1.54 s |

## Honest costs (the price of the two indexes)

The provenance index (ADR-022) and, when enabled, the unicode tokenizer (ADR-023) are not free.
Measured against v0.2.0:

| metric | v0.2.0 | v0.3 | delta |
|---|---|---|---|
| write throughput @100k | ~9 300 facts/s | ~6 400 facts/s | **~1.45× slower** |
| DB size @100k | 187.9 MB | 221.6 MB | **+18%** |
| `rebuild_projection` @100k | 4.45 s | 7.0 s | ~1.6× slower |
| `search` / `current` / `as_of` | — | — | unchanged |

The write and disk cost buys `explain()` at O(1). For a provenance engine, that is the right
trade. **Write amplification** on the ledger axis stays 1.0 events/fact (one sealed event per
fact); the added cost is the two secondary index writes per fact, reflected in the throughput row
above — this corrects the v0.2 docs, which implied a ~1.05× write cost and did not account for the
index writes.

**Regression caught by this benchmark, not the tests:** the first provenance-index implementation
made `rebuild_projection` @100k take **270 s** (a missing index on the idempotency `DELETE`, O(N²)).
All 655 tests passed at 270 s; the benchmark is what exposed it. Fixed with `idx_prov_ref_seq`
(ADR-022), bringing it to 7 s.

## Recall bound (documented trade-off, ADR-017)

`CANDIDATE_POOL = 500` bounds recall for very high-frequency terms: at 100k, a term present in 2000
objects returns the top 500 by BM25, re-ranked by the full score. This is unchanged from v0.2 and is
a deliberate latency/recall trade; it is disclosed, not hidden (`retrieval_method` reports the path).

## Unicode tokenizer (ADR-023, opt-in)

| metric | ascii (default) | unicode |
|---|---|---|
| non-ASCII search (`Tóquio`, `café`, `Ольга`, `日本語`) | 0 hits | works |
| build 10k | 1.16 s | 1.20 s (+3%) |
| per-query tokenizer cost (rare term) | ~0.02 ms | ~0.09 ms |
| scan/index parity (120-query multilingual fuzz) | — | 0 divergences |

## Limits honestly stated

- **1M not measured.** The census tops out at 100k on this machine within the mission window;
  `BENCH_LIMIT = 100k` is stated rather than extrapolated. The flat `explain()`/`current()`/`as_of()`
  curves suggest 1M would hold, but that is **inferred, not measured**.
- All numbers are single-machine, single-process, warm SQLite page cache. They are for relative
  comparison (before/after, scan/index), not absolute SLAs.

`BENCHMARK = PASS` — before/after measured for every performance change; costs disclosed.
