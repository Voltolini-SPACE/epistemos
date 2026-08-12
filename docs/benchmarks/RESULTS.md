# EPISTEMOS Benchmark Results

Reproducible: `python benchmarks/bench.py --scales 1000 10000 100000`

## Hardware / configuration

- **platform**: macOS-26.3.1-arm64-arm-64bit-Mach-O
- **machine**: arm64
- **python**: 3.14.5
- **cpu_count**: 10
- **store**: SQLite (WAL, `synchronous=FULL`), single file, zero-egress
- **methodology**: dataset seeded with `synchronous=OFF` (not timed); measured writes use `synchronous=FULL` (fsync/commit).

## Latency (milliseconds) by scale

| scale | events | write p50 | write p99 | read p50 | temporal p50 | graph3 p50 | search p50 | explain p50 | startup | db size | peak mem |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1,000 | 2,149 | 0.6992 | 5.3539 | 6.1499 | 6.1805 | 0.9503 | 0.1281 | 0.158 | 47.811 ms | 4.2 MB | 1.1 MB |
| 10,000 | 11,149 | 0.5772 | 4.0309 | 5.7825 | 5.8257 | 0.9487 | 0.1387 | 0.1509 | 241.285 ms | 21.4 MB | 1.1 MB |

## Collaborative claims (EPISTEMOS-05) latency by scale

| scale | claim create p50 | claim create p99 | belief p50 | explain_claim p50 |
|---|---|---|---|---|
| 1,000 | 0.775 | 2.2505 | 0.7165 | 1.4643 |
| 10,000 | 0.5673 | 1.019 | 0.6656 | 1.3575 |

## Observations

- Write latency is dominated by the per-commit `fsync` (durability), not by dataset size — it is roughly flat across scales, as expected for an append + indexed-upsert in one transaction.
- `search` is a full-scan lexical scorer (no ANN index); its latency grows with scale. This is the first place a vector/FTS index would be added if a measured workload demanded it (ADR-007 keeps it a pluggable port).
- Exact read / temporal / graph / explain stay low because they are indexed lookups and bounded traversals.

Raw JSON per scale:

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
      "events": 2149,
      "seed_throughput_writes_per_s": 2091.7,
      "write_full_durability": {
        "p50_ms": 0.6992,
        "p95_ms": 1.992,
        "p99_ms": 5.3539,
        "n": 300
      },
      "read_current": {
        "p50_ms": 6.1499,
        "p95_ms": 7.2711,
        "p99_ms": 10.7011,
        "n": 300
      },
      "temporal_as_of": {
        "p50_ms": 6.1805,
        "p95_ms": 7.2789,
        "p99_ms": 9.165,
        "n": 300
      },
      "graph_traversal_3hops": {
        "p50_ms": 0.9503,
        "p95_ms": 1.3413,
        "p99_ms": 6.5431,
        "n": 50
      },
      "search": {
        "p50_ms": 0.1281,
        "p95_ms": 0.7033,
        "p99_ms": 1.7393,
        "n": 50
      },
      "explain": {
        "p50_ms": 0.158,
        "p95_ms": 0.2007,
        "p99_ms": 0.6198,
        "n": 50
      },
      "claim_create": {
        "p50_ms": 0.775,
        "p95_ms": 1.1471,
        "p99_ms": 2.2505,
        "n": 50
      },
      "claim_belief": {
        "p50_ms": 0.7165,
        "p95_ms": 0.8488,
        "p99_ms": 0.9351,
        "n": 50
      },
      "claim_explain": {
        "p50_ms": 1.4643,
        "p95_ms": 2.0088,
        "p99_ms": 2.5417,
        "n": 50
      },
      "startup_ms": 47.811,
      "db_size_bytes": 4423680,
      "python_peak_mem_mb": 1.1,
      "wall_seconds": 5.4
    },
    {
      "scale": 10000,
      "events": 11149,
      "seed_throughput_writes_per_s": 1902.6,
      "write_full_durability": {
        "p50_ms": 0.5772,
        "p95_ms": 1.0086,
        "p99_ms": 4.0309,
        "n": 300
      },
      "read_current": {
        "p50_ms": 5.7825,
        "p95_ms": 6.9367,
        "p99_ms": 9.7819,
        "n": 300
      },
      "temporal_as_of": {
        "p50_ms": 5.8257,
        "p95_ms": 6.8106,
        "p99_ms": 8.7981,
        "n": 300
      },
      "graph_traversal_3hops": {
        "p50_ms": 0.9487,
        "p95_ms": 0.9643,
        "p99_ms": 4.6571,
        "n": 50
      },
      "search": {
        "p50_ms": 0.1387,
        "p95_ms": 0.3672,
        "p99_ms": 2.76,
        "n": 50
      },
      "explain": {
        "p50_ms": 0.1509,
        "p95_ms": 0.1599,
        "p99_ms": 0.2668,
        "n": 50
      },
      "claim_create": {
        "p50_ms": 0.5673,
        "p95_ms": 0.6491,
        "p99_ms": 1.019,
        "n": 50
      },
      "claim_belief": {
        "p50_ms": 0.6656,
        "p95_ms": 0.6982,
        "p99_ms": 0.7706,
        "n": 50
      },
      "claim_explain": {
        "p50_ms": 1.3575,
        "p95_ms": 1.447,
        "p99_ms": 2.152,
        "n": 50
      },
      "startup_ms": 241.285,
      "db_size_bytes": 22417408,
      "python_peak_mem_mb": 1.1,
      "wall_seconds": 10.0
    }
  ]
}
```
