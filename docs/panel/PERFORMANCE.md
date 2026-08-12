# Performance

Measured, not asserted (mission §27). Hardware: the development Mac (Apple Silicon), Python 3.14.

## Boundary (server-side, measured)

| workload | result |
|----------|--------|
| knowledge graph, 1,000 authorized nodes | assembled in **~50 ms** |
| knowledge graph, 10,000 candidates | capped to **1,500 nodes** in **~700 ms** (`truncated=true` reported) |
| search over 100,000 facts (SQLite FTS store) | **~34 ms** (the core's FTS index) |
| search over 100,000 facts (in-memory scan store) | **~1.3 s** (linear scan; the demo store) |

Search latency is the core's — the panel adds only per-hit label enrichment. Large deployments use the
SQLite/FTS store (~34 ms @ 100k); the in-memory demo store scans.

## Frontend (canvas, measured in-browser)

| workload | result |
|----------|--------|
| render one frame @ 1,000 nodes | **~0.2 ms** |
| render one frame @ 1,500 nodes (the cap) | **~0.2 ms** |
| render one frame @ 10,000 nodes (synthetic) | **~1.9 ms** |
| initial layout settle @ 1,500 nodes, reduced-motion | **~0.8 s**, time-budgeted (never blocks) |

The renderer is cheap because of **viewport culling** (only visible nodes drawn), **level-of-detail**
(labels/edges drop out when zoomed far), and **spatial-grid repulsion** (~O(n) physics). The DOM never
holds 100k nodes — the graph is a single canvas, and lists/tables are bounded and virtualizable.

## Techniques (mission §27/§28)

- No 100k DOM nodes — canvas for the graph, bounded/paged tables elsewhere.
- Graph render cap (1,500) with honest `truncated` disclosure; explore larger via focused `expand`.
- Level-of-detail by zoom; viewport culling; spatial-grid physics.
- Reduced-motion layout is time-budgeted so a large graph never freezes the main thread.

## Known limits / next work

Cluster/aggregation rendering for genuine 10k+ single-view exploration (distant-zoom clusters, §28) is
future work; today the cap + focused expansion cover exploration within the authorized set. An
automated Lighthouse/FPS harness in CI is the recommended next measurement.
