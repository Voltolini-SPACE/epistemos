<p align="center">
  <img src="docs/brand/assets/logo-horizontal.svg" alt="EPISTEMOS" width="380"/>
</p>

<p align="center"><strong>Sovereign, graph-native context, memory, provenance and decision-lineage engine for AI agents.</strong></p>

<p align="center">
  <a href="https://voltolini.space/epistemos">Website</a> ·
  <a href="docs/adr/README.md">Architecture (ADRs)</a> ·
  <a href="https://github.com/Voltolini-SPACE/epistemos/releases">Releases</a> ·
  MIT · Python ≥3.11 · <strong>zero runtime dependencies</strong>
</p>

---

EPISTEMOS is the layer that answers *what the system knows, how it knows it, when it
knew it, and where that knowledge came from* — independent of any single LLM, provider,
agent framework, vector database or graph database.

> NOMOS decides **what an agent may do**. EPISTEMOS records **what the system knows** —
> and can be used by NOMOS, Hermes, OpenClaw, or any other agent without becoming a
> mandatory dependency of any of them. (Those integrations are **adapter-ready / planned**,
> not yet shipped.)

## Status

**`v0.3.0` — developer preview.** Clean-room, not a fork or submodule of any system.
Adversarially audited (43 findings fixed), **700 tests**, mutation **25/25** killed,
ruff + mypy `--strict` clean. See [`docs/STATUS.md`](docs/STATUS.md) for the full gate matrix.

**Measured, reproducible** (`benchmarks/`):
- 100k lexical **search: 6.2 s → 34 ms (~183×)** vs the O(N) scan (v0.2, FTS5 index).
- `explain()` **provenance: ~1.9 s → ~0.05 ms at 100k (~33,800×)** (v0.3, provenance index).
- Write latency stays ~0.4 ms; the core makes **no network calls** and needs **no LLM**.

## Design principles (enforced, not aspirational)

1. **Local-first** — the core runs on a single machine with the standard library only.
2. **Zero-egress by default** — the core makes **no** network calls. Proven by test.
3. **Model-agnostic** — no LLM is required for any core operation. A `NullModelProvider`
   proves the core works with no model at all.
4. **Storage-agnostic** — the domain depends on *ports*, never on SQLite/Neo4j/pgvector.
5. **Agent-agnostic** — Claude, OpenAI, Hermes, OpenClaw are *clients*, never the core.
6. **Graph-native** — entities and relations are first-class objects.
7. **Temporal-native (bitemporal)** — every fact carries **valid time** (when it is true
   in the world) and **transaction time** (when the system believed it). Time is not
   decorative metadata.
8. **Provenance-first** — every relevant fact can answer *WHERE DID THIS COME FROM?*
9. **Explainable retrieval** — every result can answer *WHY WAS THIS RETURNED?*
10. **Decision lineage** — every recorded decision can answer *WHAT EVIDENCE LED TO THIS?*
11. **Contradiction-aware** — new facts never silently delete old ones; genealogy is kept.
12. **Append-oriented history** — a hash-chained, tamper-evident event ledger is the truth.
13. **Multi-tenant by design** — tenant/principal/namespace on every read and write.
14. **Fail-closed** — unknown tenant, authorization, source, schema or integrity ⇒ refuse.

## Quickstart

```python
from epistemos import Engine, Principal

eng = Engine.open("knowledge.epistemos")          # single local file, no network
ctx = Principal(tenant="acme", agent="claude", namespace="hr")

# assert a fact with provenance and valid-time
src = eng.add_source(ctx, uri="mem://note-1", kind="note", trust=0.6)
f = eng.assert_fact(ctx, subject="Alice", predicate="works_at", object="X",
                    valid_from="2026-01-01", source=src.id)

# later: Alice leaves X on 2026-02-01. Model this by ENDING the fact's world-validity —
# the value X is preserved over [2026-01-01, 2026-02-01), so history is not lost.
# (Use supersede() instead when the *value* was wrong and should be replaced.)
eng.end_fact(ctx, f.id, valid_to="2026-02-01", reason="Alice left X")

eng.current(ctx, subject="Alice", predicate="works_at")   # -> None (not valid now)
eng.as_of(ctx, "2026-01-15", subject="Alice", predicate="works_at")  # -> "X" (she worked there then)
eng.explain(ctx, f.id)                                     # -> provenance genealogy
```

## Architecture

```
   NOMOS ─(adapter)─┐
   HERMES ──────────┤          ┌───────────── EPISTEMOS core ─────────────┐
   OpenClaw ────────┼─ SDK ───▶│ model · graph · temporal · provenance    │
   other agents ────┘  REST    │ memory · retrieval · decisions · ledger  │
                        MCP     │ identity/tenancy (fail-closed)           │
                                └──────────────────┬───────────────────────┘
                                                   │  storage ports
                                 ┌─────────────────▼─────────────────┐
                                 │ SQLite adapter · in-memory adapter │
                                 └────────────────────────────────────┘
```

The core (`src/epistemos/`) depends only on ports. Adapters depend on EPISTEMOS —
never the reverse (`CORE ← ADAPTER`, never `CORE → NOMOS`).

## What it is (and is not)

**What is EPISTEMOS?** A sovereign, local-first engine for context, memory, provenance and
decision-lineage — an append-only, hash-chained, **bitemporal** knowledge store with explainable
retrieval, usable by any agent via SDK, REST, or MCP.

**What is it *not*?** It is **not** an executor, a PDP, a policy authority, an orchestrator, a
sandbox, or a substitute for NOMOS. It does not decide what an agent may do — it records what the
system knows. It is not an LLM wrapper: the core needs no model.

**Why does it exist?** Because agent memory today couples knowledge to a specific LLM/vendor/vector-DB,
mutates state in place (losing history), severs provenance at ingest, and treats memory as a database
rather than a replayed-into-context **injection sink**. EPISTEMOS fixes all four (see
[`docs/research/EPISTEMOS_RESEARCH_FINAL.md`](docs/research/EPISTEMOS_RESEARCH_FINAL.md)).

**Why not just a vector DB?** A vector DB gives fuzzy recall with no time, no provenance, no
supersession, and opaque scores. EPISTEMOS answers *when a fact was true*, *when we believed it*,
*where it came from*, and *why a result was returned* — and works with **no** embeddings.

**Why not just a graph DB?** A graph DB gives you nodes/edges but not bitemporality, not tamper-evident
provenance, not fail-closed tenancy, and usually a Cypher/SPARQL injection surface. EPISTEMOS is
graph-native *plus* those properties, with no query language to inject into.

**Why not Graphiti / Semantica / Mem0 / …?** They are excellent at parts (Graphiti's bitemporal edge,
TrustGraph's PROV-O, Semantica's decision nodes) but every LLM-native one puts the model on the write
path (non-deterministic, cloud-bound, poisonable) and none content-hashes its provenance or enforces
fail-closed tenancy. EPISTEMOS keeps the good ideas and designs out the shared mistakes
([`COMPETITOR_MATRIX.md`](docs/research/COMPETITOR_MATRIX.md)).

**How does temporal memory work?** Every fact carries *valid time* and *transaction time*. Supersession
closes belief without deleting; `current` asks "true & believed now", `as_of(V, T)` asks "what did we
believe at T about world-time V". See [`ADR-003`](docs/adr/ADR-003-temporal-model.md).

**How does provenance work?** Every object maps to W3C PROV Entity/Activity/Agent; `explain(id)` walks
the derivation genealogy and cross-references the tamper-evident ledger. See
[`ADR-004`](docs/adr/ADR-004-provenance-model.md).

**How does tenancy work?** Every call carries a `Principal` (tenant/agent/namespace). Cross-scope access
fails closed; agent-private memory is a per-agent namespace. See
[`ADR-008`](docs/adr/ADR-008-identity-tenancy.md).

**How to run locally?** `Engine.open("knowledge.epistemos")` (one SQLite file) or `Engine.open(":memory:")`.
No server, no network, no model. Run `python examples/quickstart.py`.

**How to export all data?** `engine.export()` → a versioned JSON event log (full history + provenance).
Re-importable with integrity verification. EPISTEMOS is not a data prison.

**How to remove it?** Delete the single `*.epistemos` / `*.db` file (and its `-wal`/`-shm` sidecars) and
`pip uninstall epistemos`. Nothing else is touched; no daemon, no system state, no external service.

## Documentation

- `docs/research/` — competitor census, feature harvest, final research report
- `docs/spec/` — [core data model](docs/spec/CORE_MODEL.md), [memory model](docs/spec/MEMORY_MODEL.md)
- `docs/adr/` — [architecture decision records](docs/adr/README.md) (ADR-001 … ADR-015)
- `docs/security/` — [threat model](docs/security/THREAT_MODEL.md), license matrix, SBOM, zero-egress,
  mutation report
- `docs/benchmarks/` — [reproducible benchmark](docs/benchmarks/RESULTS.md) methodology and results
- `docs/STATUS.md` — the gate matrix and evidence (v0.1 + v0.2)

> **v0.2 (SCALE-RETRIEVAL)** replaces the v0.1 O(N) text search with a rebuildable, tenant/temporal-
> aware **FTS5 index** (~180×–200× faster at 1k–100k; 100k search ≈ 4.7 s → 28 ms) while preserving
> explainability, temporal semantics, provenance, tenancy and zero-egress. The scan remains the
> correctness reference and safe fallback. See
> [`docs/EPISTEMOS_V0_2_FINAL_REPORT.md`](docs/EPISTEMOS_V0_2_FINAL_REPORT.md) and ADR-016…020.
>
> **v0.3 (AUDIT + UPLIFT)** re-audited v0.2 adversarially and fixed every material defect (two
> cross-tenant leaks, a bitemporal history-rewrite, retrieval-fallback semantics, agent-isolation
> gaps, index-health blindness), then added a rebuildable **provenance index** — `explain()` goes
> from O(ledger) (1.9 s at 100k) to **flat ~0.05 ms** (ADR-022) — **opt-in unicode search**
> (`Engine.open(tokenizer="unicode")`, ADR-023), and a retrieval-semantics fix so a degraded index
> answers the *same question* as a healthy one (ADR-021). 700 tests, mutation 25/25, zero runtime
> deps preserved. It also assesses (design only) evolving EPISTEMOS into collaborative/federated
> knowledge infrastructure without sacrificing local-first — see
> [`docs/EPISTEMOS_V0_3_FINAL_REPORT.md`](docs/EPISTEMOS_V0_3_FINAL_REPORT.md),
> [`docs/audit/EPISTEMOS_V0_2_AUDIT.md`](docs/audit/EPISTEMOS_V0_2_AUDIT.md), and
> [`docs/collaboration/`](docs/collaboration/COLLABORATIVE_KNOWLEDGE_MODEL.md).

## License

MIT. EPISTEMOS has **zero third-party runtime dependencies** by design (stdlib only).
Clean-room implementation — not a fork, no copied code
([attestation](docs/security/LICENSE_MATRIX.md)).
