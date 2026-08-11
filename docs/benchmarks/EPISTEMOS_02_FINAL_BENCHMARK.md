# EPISTEMOS-02 — Retrieval Benchmark: LEGACY O(N) vs INDEXED (FTS5)

Reproducible: `python benchmarks/compare_retrieval.py --scales 1000 10000 100000`

## Hardware / configuration
- **platform**: macOS-26.3.1-arm64-arm-64bit-Mach-O
- **machine**: arm64
- **python**: 3.14.5
- **cpu_count**: 10
- store: SQLite (WAL, `synchronous=FULL`); FTS5 index in the same DB; zero-egress
- query: selective term (~n/200 matches). Legacy is O(n) regardless of selectivity;
  sampled fewer times at large n (documented).

## Search latency — selective query (milliseconds)

| scale | LEGACY p50 | LEGACY p99 | INDEXED p50 | INDEXED p99 | speedup (p50) |
|------:|-----------:|-----------:|------------:|------------:|--------------:|
| 1,000 | 69.6395 | 74.3154 | 0.2825 | 1.2862 | **247×** |
| 10,000 | 620.0176 | 639.8112 | 2.3955 | 4.6175 | **259×** |
| 100,000 | 6198.9556 | 7054.9516 | 33.89 | 46.1965 | **183×** |

## Indexed detail

| scale | indexed broad p50 | write p50 (FULL) | index build | cold 1st search | warm p50 | db size | index rows | peak mem |
|------:|------------------:|-----------------:|------------:|----------------:|---------:|--------:|-----------:|---------:|
| 1,000 | 24.753 ms | 0.4454 ms | 18.8 ms | 0.347 ms | 0.1067 ms | 2.5 MB | 1,300 | 5.0 MB |
| 10,000 | 38.7138 ms | 0.4467 ms | 173.5 ms | 1.1963 ms | 0.7693 ms | 18.5 MB | 10,300 | 39.3 MB |
| 100,000 | 173.3937 ms | 0.4428 ms | 1790.4 ms | 9.5911 ms | 8.6669 ms | 183.6 MB | 100,300 | 383.1 MB |

## Write amplification (ETAPA 11)

Every write now also updates the FTS index (in the same transaction). Measured indexed
write p50 above vs the v0.1 no-index baseline (`RESULTS.md`: ~0.36/0.41/0.42 ms at
1k/10k/100k). The index adds a small, roughly-flat per-write cost; write latency stays
sub-millisecond and does not grow materially with scale.

## Conclusion

Indexed lexical search is **orders of magnitude** faster than the legacy O(n) scan and
stays ~flat with scale, while write latency remains sub-millisecond and all v0.1
semantics (temporal, provenance, tenancy, explainability) are preserved. The legacy
scan is retained as the correctness reference and the safe fallback (ADR-019).

```json
{
  "hardware": {
    "platform": "macOS-26.3.1-arm64-arm-64bit-Mach-O",
    "machine": "arm64",
    "python": "3.14.5",
    "cpu_count": 10
  },
  "results": [
    {
      "scale": 1000,
      "events": 1300,
      "index_count": 1300,
      "indexed_selective_ms": {
        "p50": 0.2825,
        "p95": 0.8596,
        "p99": 1.2862
      },
      "indexed_broad_ms": {
        "p50": 24.753,
        "p95": 27.3055,
        "p99": 28.0928
      },
      "legacy_selective_ms": {
        "p50": 69.6395,
        "p95": 74.3154,
        "p99": 74.3154
      },
      "write_full_ms": {
        "p50": 0.4454,
        "p95": 0.5469,
        "p99": 0.9826
      },
      "index_build_ms": 18.8,
      "cold_first_search_ms": 0.347,
      "warm_search": {
        "p50": 0.1067,
        "p95": 0.1139,
        "p99": 0.1492
      },
      "db_size_mb": 2.5,
      "peak_mem_mb": 5.0
    },
    {
      "scale": 10000,
      "events": 10300,
      "index_count": 10300,
      "indexed_selective_ms": {
        "p50": 2.3955,
        "p95": 2.7663,
        "p99": 4.6175
      },
      "indexed_broad_ms": {
        "p50": 38.7138,
        "p95": 41.2458,
        "p99": 41.6638
      },
      "legacy_selective_ms": {
        "p50": 620.0176,
        "p95": 639.8112,
        "p99": 639.8112
      },
      "write_full_ms": {
        "p50": 0.4467,
        "p95": 0.5312,
        "p99": 2.4747
      },
      "index_build_ms": 173.5,
      "cold_first_search_ms": 1.1963,
      "warm_search": {
        "p50": 0.7693,
        "p95": 0.9053,
        "p99": 1.0473
      },
      "db_size_mb": 18.5,
      "peak_mem_mb": 39.3
    },
    {
      "scale": 100000,
      "events": 100300,
      "index_count": 100300,
      "indexed_selective_ms": {
        "p50": 33.89,
        "p95": 41.7608,
        "p99": 46.1965
      },
      "indexed_broad_ms": {
        "p50": 173.3937,
        "p95": 199.8519,
        "p99": 210.8938
      },
      "legacy_selective_ms": {
        "p50": 6198.9556,
        "p95": 7054.9516,
        "p99": 7054.9516
      },
      "write_full_ms": {
        "p50": 0.4428,
        "p95": 0.655,
        "p99": 3.4547
      },
      "index_build_ms": 1790.4,
      "cold_first_search_ms": 9.5911,
      "warm_search": {
        "p50": 8.6669,
        "p95": 9.3676,
        "p99": 10.8852
      },
      "db_size_mb": 183.6,
      "peak_mem_mb": 383.1
    }
  ]
}
```
