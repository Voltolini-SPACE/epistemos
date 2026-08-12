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
| 1,000 | 47.7038 | 53.4088 | 0.2601 | 0.4217 | **183×** |
| 10,000 | 425.0045 | 489.1744 | 2.2332 | 2.7988 | **190×** |
| 100,000 | 4738.3966 | 5165.2312 | 28.0235 | 33.0571 | **169×** |

## Indexed detail

| scale | indexed broad p50 | write p50 (FULL) | index build | cold 1st search | warm p50 | db size | index rows | peak mem |
|------:|------------------:|-----------------:|------------:|----------------:|---------:|--------:|-----------:|---------:|
| 1,000 | 25.0665 ms | 0.4678 ms | 33.1 ms | 0.286 ms | 0.1068 ms | 2.7 MB | 1,300 | 4.5 MB |
| 10,000 | 36.8608 ms | 0.4798 ms | 266.5 ms | 1.1387 ms | 0.7426 ms | 20.1 MB | 10,300 | 34.4 MB |
| 100,000 | 179.2455 ms | 0.5022 ms | 4549.4 ms | 11.2051 ms | 9.5177 ms | 199.7 MB | 100,300 | 334.8 MB |

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
        "p50": 0.2601,
        "p95": 0.2897,
        "p99": 0.4217
      },
      "indexed_broad_ms": {
        "p50": 25.0665,
        "p95": 27.5655,
        "p99": 27.7193
      },
      "legacy_selective_ms": {
        "p50": 47.7038,
        "p95": 53.4088,
        "p99": 53.4088
      },
      "write_full_ms": {
        "p50": 0.4678,
        "p95": 0.5542,
        "p99": 1.1624
      },
      "index_build_ms": 33.1,
      "cold_first_search_ms": 0.286,
      "warm_search": {
        "p50": 0.1068,
        "p95": 0.1537,
        "p99": 0.3655
      },
      "db_size_mb": 2.7,
      "peak_mem_mb": 4.5
    },
    {
      "scale": 10000,
      "events": 10300,
      "index_count": 10300,
      "indexed_selective_ms": {
        "p50": 2.2332,
        "p95": 2.4888,
        "p99": 2.7988
      },
      "indexed_broad_ms": {
        "p50": 36.8608,
        "p95": 39.2905,
        "p99": 39.887
      },
      "legacy_selective_ms": {
        "p50": 425.0045,
        "p95": 489.1744,
        "p99": 489.1744
      },
      "write_full_ms": {
        "p50": 0.4798,
        "p95": 0.608,
        "p99": 3.2836
      },
      "index_build_ms": 266.5,
      "cold_first_search_ms": 1.1387,
      "warm_search": {
        "p50": 0.7426,
        "p95": 0.8604,
        "p99": 1.0248
      },
      "db_size_mb": 20.1,
      "peak_mem_mb": 34.4
    },
    {
      "scale": 100000,
      "events": 100300,
      "index_count": 100300,
      "indexed_selective_ms": {
        "p50": 28.0235,
        "p95": 31.6492,
        "p99": 33.0571
      },
      "indexed_broad_ms": {
        "p50": 179.2455,
        "p95": 196.7371,
        "p99": 205.4525
      },
      "legacy_selective_ms": {
        "p50": 4738.3966,
        "p95": 5165.2312,
        "p99": 5165.2312
      },
      "write_full_ms": {
        "p50": 0.5022,
        "p95": 0.7119,
        "p99": 4.5052
      },
      "index_build_ms": 4549.4,
      "cold_first_search_ms": 11.2051,
      "warm_search": {
        "p50": 9.5177,
        "p95": 10.9129,
        "p99": 12.8457
      },
      "db_size_mb": 199.7,
      "peak_mem_mb": 334.8
    }
  ]
}
```
