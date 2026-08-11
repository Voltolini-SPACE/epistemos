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
| 1,000 | 1,999 | 0.3602 | 0.88 | 5.5944 | 5.5606 | 0.6807 | 107.7495 | 102.5458 | 1.111 ms | 2.9 MB | 7.5 MB |
| 10,000 | 10,999 | 0.4142 | 1.9968 | 5.8071 | 5.862 | 0.7669 | 698.2131 | 704.941 | 3.587 ms | 16.9 MB | 44.0 MB |
| 100,000 | 100,999 | 0.4175 | 1.1553 | 5.7474 | 5.7227 | 0.7975 | 7220.4476 | 7035.8467 | 24.781 ms | 156.5 MB | 409.1 MB |

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
      "events": 1999,
      "seed_throughput_writes_per_s": 3072.1,
      "write_full_durability": {
        "p50_ms": 0.3602,
        "p95_ms": 0.4002,
        "p99_ms": 0.88,
        "n": 300
      },
      "read_current": {
        "p50_ms": 5.5944,
        "p95_ms": 6.0182,
        "p99_ms": 6.19,
        "n": 300
      },
      "temporal_as_of": {
        "p50_ms": 5.5606,
        "p95_ms": 5.8723,
        "p99_ms": 16.2673,
        "n": 300
      },
      "graph_traversal_3hops": {
        "p50_ms": 0.6807,
        "p95_ms": 0.7527,
        "p99_ms": 0.8802,
        "n": 50
      },
      "search": {
        "p50_ms": 107.7495,
        "p95_ms": 113.4275,
        "p99_ms": 114.4841,
        "n": 50
      },
      "explain": {
        "p50_ms": 102.5458,
        "p95_ms": 108.8613,
        "p99_ms": 113.729,
        "n": 50
      },
      "startup_ms": 1.111,
      "db_size_bytes": 3055616,
      "python_peak_mem_mb": 7.5,
      "wall_seconds": 14.7
    },
    {
      "scale": 10000,
      "events": 10999,
      "seed_throughput_writes_per_s": 2677.8,
      "write_full_durability": {
        "p50_ms": 0.4142,
        "p95_ms": 0.5663,
        "p99_ms": 1.9968,
        "n": 300
      },
      "read_current": {
        "p50_ms": 5.8071,
        "p95_ms": 6.4516,
        "p99_ms": 6.7178,
        "n": 300
      },
      "temporal_as_of": {
        "p50_ms": 5.862,
        "p95_ms": 6.426,
        "p99_ms": 6.5499,
        "n": 300
      },
      "graph_traversal_3hops": {
        "p50_ms": 0.7669,
        "p95_ms": 1.3707,
        "p99_ms": 4.0983,
        "n": 50
      },
      "search": {
        "p50_ms": 698.2131,
        "p95_ms": 730.6419,
        "p99_ms": 790.4363,
        "n": 50
      },
      "explain": {
        "p50_ms": 704.941,
        "p95_ms": 727.4035,
        "p99_ms": 753.6913,
        "n": 50
      },
      "startup_ms": 3.587,
      "db_size_bytes": 17674240,
      "python_peak_mem_mb": 44.0,
      "wall_seconds": 78.0
    },
    {
      "scale": 100000,
      "events": 100999,
      "seed_throughput_writes_per_s": 2592.2,
      "write_full_durability": {
        "p50_ms": 0.4175,
        "p95_ms": 0.5621,
        "p99_ms": 1.1553,
        "n": 300
      },
      "read_current": {
        "p50_ms": 5.7474,
        "p95_ms": 6.5657,
        "p99_ms": 6.8444,
        "n": 300
      },
      "temporal_as_of": {
        "p50_ms": 5.7227,
        "p95_ms": 6.457,
        "p99_ms": 6.7575,
        "n": 300
      },
      "graph_traversal_3hops": {
        "p50_ms": 0.7975,
        "p95_ms": 0.8203,
        "p99_ms": 0.828,
        "n": 50
      },
      "search": {
        "p50_ms": 7220.4476,
        "p95_ms": 7492.647,
        "p99_ms": 7509.3756,
        "n": 50
      },
      "explain": {
        "p50_ms": 7035.8467,
        "p95_ms": 7357.5348,
        "p99_ms": 7607.6171,
        "n": 50
      },
      "startup_ms": 24.781,
      "db_size_bytes": 164130816,
      "python_peak_mem_mb": 409.1,
      "wall_seconds": 752.5
    }
  ]
}
```
