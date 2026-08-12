# ADR-035 — Contradiction pinning (authorization-safe)

**Status:** Accepted (v0.6.0)

## Context

A contradiction is the most expensive object to lose from a context — it flips an answer. Two ways
to lose one during compaction: (a) fold or drop it, or (b) *fail to surface it* because it was
attached to a retrieved claim rather than being a top hit itself. And the fix for (b) opens a leak:
a contradiction attached to a *shared* claim may itself be *private*.

## Decision

**Pin** contradictions so they are always delivered inline and never folded or dropped.

- Pin every contradiction that is **retrieved** (`kind == evidence`,
  `metadata.relation ∈ {contradicts, weakens}`) **or attached to a retrieved claim** via that claim's
  `metadata.evidence_links`.
- The attached case is the *only* relation the envelope follows beyond raw retrieval. Each attached
  contradiction is **re-authorized** with `is_readable` for the requesting principal before pinning —
  so a private contradiction on a shared claim never leaks.
- Pinned contradictions survive redundancy collapse and experimental budget packing
  unconditionally. If a contradiction the baseline could reach is not delivered (e.g. filtered by
  authorization), the envelope declares `context_incomplete` instead of hiding it.

## Consequences

- `CONTRADICTION_LOSS = 0` and `PRIVATE_CONTEXT_LEAK = 0` are both enforced on this path.
- Mutation gate kills both "pin removed" (M1) and "attached-contradiction authz removed" (M3).
- Benchmark: `CONTRADICTION_LOSS = 0` at 1000+ state changes.

## Alternatives rejected

- **Pin only retrieved contradictions** — misses a contradiction attached to a retrieved claim.
- **Follow attached contradictions without re-authorization** — leaks private contradictions on
  shared claims.
