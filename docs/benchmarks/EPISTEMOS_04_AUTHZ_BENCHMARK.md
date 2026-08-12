# EPISTEMOS v0.4 — Authorization Overhead Benchmark

**Machine:** Apple Silicon, 10 cores. **Python:** 3.14.5. **Backend:** SQLite (WAL, synchronous=FULL).
Harness: `scratchpad/bench_authz.py`. Mission §31: measure the cost of the space firewall vs the v0.3
retrieval path; **security is not traded for speed**.

Two corpora: **private** (single-agent, every object PRIVATE — the common local-first case) and
**org** (every fact promoted to a tenant-wide ORGANIZATION space — the worst case for the space
lookup, one placement resolved per candidate). p50 unless noted.

| corpus | scale | build | writes/s | search (common term) | search (rare) | current | get |
|--------|------:|------:|---------:|----------------------:|--------------:|--------:|----:|
| private | 1 000 | 0.10 s | 9 921 | 7.42 ms | 0.050 ms | 0.005 ms | 0.014 ms |
| private | 10 000 | 1.13 s | 8 884 | 19.13 ms | 0.060 ms | 0.006 ms | 0.014 ms |
| private | 100 000 | 15.12 s | 6 614 | 55.45 ms | 0.061 ms | 0.006 ms | 0.014 ms |
| org | 1 000 | 0.21 s | 4 870 | 8.59 ms | 0.074 ms | 0.006 ms | 0.019 ms |
| org | 10 000 | 2.24 s | 4 462 | 20.76 ms | 0.070 ms | 0.006 ms | 0.020 ms |
| org | 100 000 | 28.83 s | 3 469 | 58.00 ms | 0.085 ms | 0.006 ms | 0.020 ms |

## Reading

- **Common-term search** (a term matching ~1/8 of the corpus) at 100k: **55 ms private** vs v0.3's
  ~34 ms — roughly **1.6×**. The cost is the per-candidate `_can_read` filter applied *before*
  scoring (the candidate-boundary-first firewall). It scales with the matched-candidate count, not
  the store size.
- **Rare-term search, `current`, `as_of`, `get`** are essentially **unchanged** (0.05–0.06 ms,
  0.006 ms, 0.014 ms) — few candidates, so the filter is negligible; `current`/`get` resolve a small
  fact set.
- **org corpus** adds a space lookup per candidate (resolve the placement's visibility): search is
  ~+5% over private; the notable cost is **writes** (~1.5–1.9× slower at scale) because each fact is
  also *promoted* (an extra ledger event + monotone check). A realistic workload promotes selectively,
  not every fact, so this is a conservative upper bound.

## Verdict

The firewall's cost is an O(matched-candidates) authorization check, disclosed and bounded. Point
reads (`get`/`current`/`as_of`) and rare-term search are unaffected; common-term search pays ~1.6×
for candidate-boundary-first authorization — the correct place to pay it (mission §12: never filter
after ranking). No security check was weakened to improve a number.

`PERFORMANCE = PASS` (authorization overhead measured, disclosed, security preserved).
