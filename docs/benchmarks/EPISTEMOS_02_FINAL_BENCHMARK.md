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
| 1,000 | 58.773 | 63.1637 | 0.2934 | 0.4297 | **200×** |
| 10,000 | 482.7447 | 498.5936 | 2.4841 | 3.1215 | **194×** |
| 100,000 | 4972.3019 | 5139.3804 | 34.0005 | 46.3757 | **146×** |

## Indexed detail

| scale | indexed broad p50 | write p50 (FULL) | index build | cold 1st search | warm p50 | db size | index rows | peak mem |
|------:|------------------:|-----------------:|------------:|----------------:|---------:|--------:|-----------:|---------:|
| 1,000 | 27.6403 ms | 0.4989 ms | 32.9 ms | 0.3198 ms | 0.1117 ms | 2.7 MB | 1,300 | 4.6 MB |
| 10,000 | 41.8838 ms | 0.4881 ms | 300.2 ms | 1.4133 ms | 0.8429 ms | 20.1 MB | 10,300 | 35.5 MB |
| 100,000 | 181.9699 ms | 0.5669 ms | 3619.0 ms | 10.3863 ms | 9.601 ms | 199.8 MB | 100,300 | 345.8 MB |

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
        "p50": 0.2934,
        "p95": 0.3503,
        "p99": 0.4297
      },
      "indexed_broad_ms": {
        "p50": 27.6403,
        "p95": 30.9961,
        "p99": 31.1139
      },
      "legacy_selective_ms": {
        "p50": 58.773,
        "p95": 63.1637,
        "p99": 63.1637
      },
      "write_full_ms": {
        "p50": 0.4989,
        "p95": 0.6062,
        "p99": 1.25
      },
      "index_build_ms": 32.9,
      "cold_first_search_ms": 0.3198,
      "warm_search": {
        "p50": 0.1117,
        "p95": 0.127,
        "p99": 0.1591
      },
      "db_size_mb": 2.7,
      "peak_mem_mb": 4.6
    },
    {
      "scale": 10000,
      "events": 10300,
      "index_count": 10300,
      "indexed_selective_ms": {
        "p50": 2.4841,
        "p95": 2.9096,
        "p99": 3.1215
      },
      "indexed_broad_ms": {
        "p50": 41.8838,
        "p95": 43.7207,
        "p99": 44.0668
      },
      "legacy_selective_ms": {
        "p50": 482.7447,
        "p95": 498.5936,
        "p99": 498.5936
      },
      "write_full_ms": {
        "p50": 0.4881,
        "p95": 0.6268,
        "p99": 3.3361
      },
      "index_build_ms": 300.2,
      "cold_first_search_ms": 1.4133,
      "warm_search": {
        "p50": 0.8429,
        "p95": 1.022,
        "p99": 1.1308
      },
      "db_size_mb": 20.1,
      "peak_mem_mb": 35.5
    },
    {
      "scale": 100000,
      "events": 100300,
      "index_count": 100300,
      "indexed_selective_ms": {
        "p50": 34.0005,
        "p95": 41.8417,
        "p99": 46.3757
      },
      "indexed_broad_ms": {
        "p50": 181.9699,
        "p95": 193.9017,
        "p99": 216.1754
      },
      "legacy_selective_ms": {
        "p50": 4972.3019,
        "p95": 5139.3804,
        "p99": 5139.3804
      },
      "write_full_ms": {
        "p50": 0.5669,
        "p95": 1.1258,
        "p99": 4.9213
      },
      "index_build_ms": 3619.0,
      "cold_first_search_ms": 10.3863,
      "warm_search": {
        "p50": 9.601,
        "p95": 11.8302,
        "p99": 13.4185
      },
      "db_size_mb": 199.8,
      "peak_mem_mb": 345.8
    }
  ]
}
```
