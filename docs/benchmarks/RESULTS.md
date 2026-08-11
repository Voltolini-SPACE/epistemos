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
| 1,000 | 1,999 | 0.3679 | 0.9211 | 5.8981 | 5.6484 | 0.7074 | 116.0425 | 108.4444 | 1.165 ms | 2.9 MB | 7.5 MB |
| 10,000 | 10,999 | 0.4073 | 2.0672 | 5.9029 | 5.8643 | 0.7657 | 721.8017 | 721.4419 | 3.917 ms | 16.8 MB | 44.0 MB |
| 100,000 | 100,999 | 0.4298 | 4.594 | 6.1862 | 6.0768 | 0.819 | 7381.0629 | 7214.0054 | 28.521 ms | 156.5 MB | 409.1 MB |

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
      "seed_throughput_writes_per_s": 2912.4,
      "write_full_durability": {
        "p50_ms": 0.3679,
        "p95_ms": 0.464,
        "p99_ms": 0.9211,
        "n": 300
      },
      "read_current": {
        "p50_ms": 5.8981,
        "p95_ms": 6.5843,
        "p99_ms": 7.0325,
        "n": 300
      },
      "temporal_as_of": {
        "p50_ms": 5.6484,
        "p95_ms": 6.4166,
        "p99_ms": 6.8867,
        "n": 300
      },
      "graph_traversal_3hops": {
        "p50_ms": 0.7074,
        "p95_ms": 0.8749,
        "p99_ms": 0.967,
        "n": 50
      },
      "search": {
        "p50_ms": 116.0425,
        "p95_ms": 120.817,
        "p99_ms": 121.9011,
        "n": 50
      },
      "explain": {
        "p50_ms": 108.4444,
        "p95_ms": 115.3312,
        "p99_ms": 116.7834,
        "n": 50
      },
      "startup_ms": 1.165,
      "db_size_bytes": 3059712,
      "python_peak_mem_mb": 7.5,
      "wall_seconds": 15.4
    },
    {
      "scale": 10000,
      "events": 10999,
      "seed_throughput_writes_per_s": 2634.7,
      "write_full_durability": {
        "p50_ms": 0.4073,
        "p95_ms": 0.4916,
        "p99_ms": 2.0672,
        "n": 300
      },
      "read_current": {
        "p50_ms": 5.9029,
        "p95_ms": 6.6383,
        "p99_ms": 6.8312,
        "n": 300
      },
      "temporal_as_of": {
        "p50_ms": 5.8643,
        "p95_ms": 6.7171,
        "p99_ms": 6.8757,
        "n": 300
      },
      "graph_traversal_3hops": {
        "p50_ms": 0.7657,
        "p95_ms": 0.8732,
        "p99_ms": 1.0085,
        "n": 50
      },
      "search": {
        "p50_ms": 721.8017,
        "p95_ms": 755.9986,
        "p99_ms": 847.6212,
        "n": 50
      },
      "explain": {
        "p50_ms": 721.4419,
        "p95_ms": 742.3036,
        "p99_ms": 746.799,
        "n": 50
      },
      "startup_ms": 3.917,
      "db_size_bytes": 17666048,
      "python_peak_mem_mb": 44.0,
      "wall_seconds": 80.4
    },
    {
      "scale": 100000,
      "events": 100999,
      "seed_throughput_writes_per_s": 2451.0,
      "write_full_durability": {
        "p50_ms": 0.4298,
        "p95_ms": 1.1095,
        "p99_ms": 4.594,
        "n": 300
      },
      "read_current": {
        "p50_ms": 6.1862,
        "p95_ms": 7.1114,
        "p99_ms": 7.592,
        "n": 300
      },
      "temporal_as_of": {
        "p50_ms": 6.0768,
        "p95_ms": 7.0302,
        "p99_ms": 7.4485,
        "n": 300
      },
      "graph_traversal_3hops": {
        "p50_ms": 0.819,
        "p95_ms": 0.8585,
        "p99_ms": 1.04,
        "n": 50
      },
      "search": {
        "p50_ms": 7381.0629,
        "p95_ms": 8516.1287,
        "p99_ms": 8671.9845,
        "n": 50
      },
      "explain": {
        "p50_ms": 7214.0054,
        "p95_ms": 8279.0758,
        "p99_ms": 8499.4943,
        "n": 50
      },
      "startup_ms": 28.521,
      "db_size_bytes": 164102144,
      "python_peak_mem_mb": 409.1,
      "wall_seconds": 787.4
    }
  ]
}
```
