# Other Projects & Standards (cross-cutting)

These are the non-competitor references whose *properties* most shaped EPISTEMOS.

## Temporal / bitemporal databases + event sourcing
**Surveyed (MEASURED):** XTDB (JUXT, MPL-2.0 — bitemporal Datalog/SQL:2011, v2 columnar),
Datomic (accumulate-only log, `as-of`), Dolt (versioned SQL), TerminusDB (immutable revision graph),
and the event-sourcing pattern.

- **Lesson:** *separate the two time axes and never conflate them.* Valid-time (true in the world)
  is independent from transaction/system-time (when the store learned it). Only bitemporality lets an
  agent answer "what did I know at T?" **and** later correct the record without destroying the audit
  trail. → EPISTEMOS models both axes on every `Fact` and tests four-corner queries.
- **Keep:** immutable accumulate-only log as source of truth; current state = a **materialized view
  rebuildable from the log**; reified transactions as the provenance anchor; supersession-not-deletion.
  → EPISTEMOS's ledger + rebuildable projection is exactly this fold-over-the-log design.
- **Mistakes to avoid:** uni-temporal foundations (painful to retrofit valid-time); mutating the
  current-state index in place (destroys reconstruction); **"immutability = safety" fallacy** — a
  poisoned/hallucinated fact in an append-only store is *permanently* trusted, so you need write-time
  provenance + trust labels + supersession, **not** delete; monotonic storage growth (needs retention).

## Provenance & ontology standards (W3C PROV / RDF / property graph)
**Surveyed (MEASURED):** W3C PROV-DM/PROV-O/PROV-N (+ PROV-JSON), RDF named graphs, RDF 1.2 triple-terms.

- **Lesson:** *separate the assertion layer from the provenance layer*, and make provenance a
  first-class **graph**, not a log. `wasDerivedFrom` closures = `explain(fact)` for free.
- **Keep:** PROV Entity/Activity/Agent as the backbone (EPISTEMOS maps object→Entity, ledger event→
  Activity, agent/principal→Agent — see ADR-004); statement-level metadata via named graphs, **not**
  classic reification; represent **contradiction by keeping both claims** with their own provenance +
  a resolution layer; export standardized PROV to avoid lock-in.
- **Mistakes to avoid:** building on pre-1.2 **RDF-star** semantics (redesigned for RDF 1.2 triple-
  terms — still Candidate Recommendation, a migration landmine); classic RDF reification; a single
  mutable scalar confidence overwritten on conflict; **treating PROV as bitemporal** (it gives
  transaction-time-ish lineage but *no* valid-time — you must add the valid-time overlay).

## MCP memory servers & local-first agent memory
**Surveyed (MEASURED):** the official MCP "memory" (Knowledge-Graph Memory) server
(`modelcontextprotocol/servers`, TypeScript, MIT) and local-first patterns.

- **Lesson — the security thesis of this whole project:** *long-term memory is an **injection sink**,
  not a database.* Anything written to memory is later replayed into the model as trusted context, so
  memory without provenance and a data/instruction boundary is a self-reinfecting prompt-injection
  channel. → EPISTEMOS treats all recalled content as **inert data**, never instructions, and every
  item carries verifiable source identity + integrity.
- **Keep:** local-first zero-external-cost default (stdio + local file); explicit minimal CRUD+retract
  tool surface; explainable retrieval; entity/relation/observation decomposition.
- **Mistakes to avoid:** flat single global namespace with **no per-principal scoping** (one caller
  owns everyone's graph + its delete primitives); provenance-free writes; timestamp-free facts;
  non-atomic full-file rewrite under concurrency. → EPISTEMOS fixes all four: fail-closed scoping,
  hashed provenance, bitemporal facts, atomic transactions.
