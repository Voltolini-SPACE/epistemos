# EPISTEMOS — Product Profile (FINAL, frozen 2026.08)

The single definition of the product. README, site, GitHub, releases and brand must not contradict
this. Freezes and supersedes the working [PRODUCT_PROFILE.md](PRODUCT_PROFILE.md).

**NAME:** EPISTEMOS

**CATEGORY:** Sovereign Context, Memory & Provenance Infrastructure for AI Agents.

**ONE-LINER:** Persistent temporal knowledge, evidence, decision lineage and evidence-preserving
context for any agent or runtime — local-first, zero-egress, no mandatory LLM.

**SHORT DESCRIPTION:** EPISTEMOS records *what a system knows, how it knows it, when it knew it, and
where that knowledge came from*, and hands any agent a compact, evidence-preserving context over the
**EPCTX/1** protocol. A bitemporal, tamper-evident knowledge base with explainable retrieval —
independent of any single LLM, vendor, vector database or graph database.

**LONG DESCRIPTION:** Agent memory today couples knowledge to one model or vector store, mutates
state in place so history is lost, severs provenance at ingest, and collapses truth into a single
confidence score. EPISTEMOS takes the opposite stance. Its source of truth is an append-only,
hash-chained ledger; all queryable state is a rebuildable projection of it. Every fact is
**bitemporal** (valid time + transaction time), so you can ask "what did we know at T?" and correct
the past without destroying the audit trail. Claims, evidence, reviews and decisions are kept
distinct and **belief is derived, never a stored boolean**. Retrieval is **explainable**, and the
**Context Envelope** compacts it without losing a contradiction, a source, or required history. The
**EPCTX/1** protocol delivers that context to any consumer over an in-process SDK, a localhost REST
API, or a hostile-boundary MCP server, with identical semantics and server-side identity. The core
makes **no network calls**, needs **no model**, and has **zero third-party runtime dependencies**;
it runs from a single local file. An operational **Panel** makes the knowledge visible and
explorable. EPISTEMOS returns context and **executes nothing** — the consumer decides how to reason;
a policy engine decides what is allowed.

**MISSION:** Give agents and runtimes a sovereign, auditable memory they own — temporal, explainable,
and traceable to its source — without surrendering it to a model, a vendor, or the cloud.

**VISION:** A world where an agent's knowledge is infrastructure, not a side effect of a model:
portable across runtimes, honest about what it knows and does not, and accountable by construction.

**PRINCIPLES:**

- **PRIVATE BY DEFAULT.** No space means private to its owner; nothing is shared implicitly.
- **SHAREABLE BY PERMISSION.** Knowledge widens only through explicit, capability-checked sharing.
- **COLLECTIVE BY VERIFICATION.** Contribution is not truth; belief is derived from evidence and
  governed review.
- **LOCAL-FIRST BY DESIGN.** Zero-egress core, no mandatory LLM, no mandatory cloud.

**STATUS AT FREEZE:** Core `v0.7.0` · Panel `v1.1` · EPCTX/1 · MIT. Integrations (NOMOS / Hermes /
OpenClaw) are **planned / spec-only**, never claimed as shipped.
