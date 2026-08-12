# EPISTEMOS — Product Profile

**NAME:** EPISTEMOS

**CATEGORY:** Sovereign Context, Memory & Provenance Infrastructure for AI Agents

**ONE-LINER:** Persistent temporal memory, explainable knowledge and decision lineage for any agent
or runtime — local-first, zero-egress, no mandatory LLM.

**SHORT DESCRIPTION:** EPISTEMOS is the layer that records *what a system knows, how it knows it,
when it knew it, and where that knowledge came from*. It gives any AI agent a bitemporal knowledge
graph with tamper-evident provenance and explainable retrieval — independent of any single LLM,
vendor, vector database or graph database.

**LONG DESCRIPTION:** Agent memory today couples knowledge to one LLM/vendor/vector-DB, mutates state
in place (losing history), severs provenance at ingest, and treats memory as a plain database rather
than as context that gets replayed into a model. EPISTEMOS takes the opposite stance. Its source of
truth is an append-only, hash-chained event ledger; all queryable state is a rebuildable projection
of it. Every fact is **bitemporal** — it carries *valid time* (when it is true in the world) and
*transaction time* (when the system believed it) — so you can ask "what did we know at T?" and
correct the past without destroying the audit trail. Every result from retrieval is **explainable**
(lexical/exact/temporal/authority/recency components + a human "why"), and every fact and decision can
answer *where did this come from?* Isolation is **fail-closed** and multi-tenant by construction, the
core makes **no network calls** and needs **no model**, and the whole runtime has **zero third-party
dependencies**. It runs from a single local file and exposes a Python SDK, a localhost REST API, and a
hostile-boundary MCP server.

**MISSION:** Give agents and runtimes a sovereign, auditable memory they own — knowledge that is
temporal, explainable, and traceable to its source, without surrendering it to a model, a vendor, or
the cloud.

**PROBLEM:** LLM-native memory systems are non-deterministic on the write path, cloud-bound, opaque in
retrieval, weak on tenancy, and lose history on contradiction. That makes agent knowledge unauditable,
un-reconstructable, and easy to poison. EPISTEMOS makes knowledge deterministic to store, temporal to
query, explainable to retrieve, and tamper-evident to trust.

**AUDIENCE:**
- agent developers
- AI infrastructure teams
- orchestration frameworks
- sovereign / self-hosted AI stacks
- local-first AI systems

**CORE CAPABILITIES:**
- temporal (bitemporal) memory
- context graph & knowledge graph
- provenance (source → observation → fact → derived fact → decision)
- decision lineage
- explainable retrieval (lexical + temporal + authority, with `why_returned`)
- multi-tenant / agent isolation (fail-closed)
- rebuildable indexes (FTS lexical + provenance index)
- local-first operation
- zero-egress by default

**EPISTEMOS IS NOT:**
- an LLM
- an agent
- an orchestrator
- a PDP / policy authority
- a vector database
- a graph database
- a NOMOS module (NOMOS, Hermes, OpenClaw are *future consumers/adapters*, never owners of the core)

**PROOF POINTS (measured, reproducible):**
- 100k lexical search: **6.2 s → 34 ms (~183×)** via a rebuildable FTS5 index (v0.2).
- `explain()` provenance: **~1.9 s → ~0.05 ms at 100k (~33,800×)** via a provenance index (v0.3).
- 700 tests · mutation 25/25 killed · adversarially audited (43 findings fixed) · zero runtime deps.

**LICENSE:** Apache-2.0 · **REPO:** https://github.com/Voltolini-SPACE/epistemos ·
**SITE:** https://voltolini.space/epistemos
