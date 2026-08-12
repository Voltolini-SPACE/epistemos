# Graph Explorer

A Canvas 2D knowledge-graph explorer (`web/graph.js`), hand-written — no d3/three/cytoscape, nothing
external. It renders the **authorized** subgraph the boundary returns (a node exists iff you can read
it; an edge iff both endpoints are readable).

## Nodes & edges

Node kinds: ENTITY, FACT, CLAIM, EVIDENCE, REVIEW, SOURCE, DECISION (+ AGENT, SPACE where present).
Edges: SUPPORTS, CONTRADICTS, WEAKENS, DERIVED_FROM, SUPERSEDES, REFERENCES, REVIEWED_BY, DECIDED_FROM
and entity relations. Node size scales with degree; claims with a non-open status get a dashed status
ring; contradiction edges are drawn thicker and red.

## Layout & scale

- **Force layout** with **spatial-grid repulsion** (bucket nodes into cells, only repel within
  neighbouring cells) → ~O(n) per tick instead of O(n²); springs along edges; gentle gravity; cooling
  alpha.
- **Viewport culling** — only nodes within the visible rectangle are drawn.
- **Level of detail** — labels appear only when zoomed in (`z > 0.85`); edges fade out when zoomed far
  out; distant zoom shows structure without label noise.
- **Render cap** — the boundary returns at most ~1500 authorized nodes and flags `truncated`; the HUD
  shows a "⚠ capped" chip. Explore larger neighbourhoods by focusing a node (`expand`), which re-runs
  the authorized filter around it.

## Interactions

zoom (wheel, to cursor) · pan (drag background) · drag node (pins it) · hover (highlight neighbourhood +
tooltip) · click (select → inspector) · double-click (expand neighbours) · pin/unpin · filter by kind
(HUD chips) · fit · fullscreen · **keyboard**: arrows move the selection between nodes, Enter opens,
`+`/`-` zoom, `f` fit. The canvas is focusable with a descriptive `aria-label`.

## Accessible alternative

The "≣ list" tool opens a **navigable table** of the same authorized graph — every node with its type
and relations, keyboard-focusable, each row opening the inspector. The graph is never the *only* way to
reach its information (a11y gate; see `ACCESSIBILITY.md`).

## Motion

New nodes enter with a brief expanding pulse, then the graph settles and goes quiet — motion means
"something changed", never decoration. Under `prefers-reduced-motion` the layout settles synchronously
(time-budgeted) and no ongoing animation runs. See `MOTION.md`, `PERFORMANCE.md`.
