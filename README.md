# EPISTEMOS

**Sovereign, graph-native context, memory, provenance and decision-lineage engine for AI agents.**

EPISTEMOS is the layer that answers *what the system knows, how it knows it, when it
knew it, and where that knowledge came from* — independent of any single LLM, provider,
agent framework, vector database or graph database.

> NOMOS decides **what an agent may do**. EPISTEMOS records **what the system knows** —
> and can be used by NOMOS, Hermes, OpenClaw, or any other agent without becoming a
> mandatory dependency of any of them.

## Status

`v0.1` — clean-room implementation. Not a fork, not a submodule of any existing system.
See [`docs/STATUS.md`](docs/STATUS.md) for the current gate matrix and evidence.

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

# later: Alice leaves X — supersede, do not delete
eng.supersede(ctx, f.id, reason="Alice left X",
              new=dict(subject="Alice", predicate="works_at", object=None,
                       valid_from="2026-02-01"))

eng.current(ctx, subject="Alice", predicate="works_at")   # -> None (she left)
eng.as_of(ctx, "2026-01-15", subject="Alice", predicate="works_at")  # -> "X"
eng.explain(f.id)                                          # -> provenance genealogy
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

## Documentation

- `docs/research/` — competitor census, feature harvest, final research report
- `docs/spec/` — core data model, temporal model, provenance model
- `docs/adr/` — architecture decision records (ADR-001 … ADR-015)
- `docs/security/` — threat model, license matrix, dependency inventory / SBOM
- `docs/benchmarks/` — reproducible benchmark methodology and results

## License

Apache-2.0. EPISTEMOS has **zero third-party runtime dependencies** by design.
