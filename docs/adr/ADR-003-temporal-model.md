# ADR-003 — Temporal model: bitemporal, half-open intervals

**Status:** Accepted (v0.1)

## Context
An agent must answer both "when was this true in the world?" and "when did the system believe it?",
and correct the past without destroying the audit trail. The census is unanimous: bitemporality is
the decisive primitive, and only Graphiti has it as a verified core model (most systems are
transaction-time-only or bolt it on).

## Decision
Every `Fact` carries **valid time** (`valid_from`/`valid_to`) and **transaction time**
(`tx_from`/`tx_to`), both as **half-open intervals `[from, to)`** with `None` = unbounded. All
temporal semantics live in one pure module (`temporal/`): `valid_at`, `believed_at`, `as_of`,
`resolve_current`. Point-in-time reconstruction combines the two axes:
`as_of(at_valid=V, at_tx=T)` = "what did the system believe at T about world-time V". Supersession
**closes** belief (`tx_to`) and never deletes. `correct_validity` performs a bitemporal correction
(preserving prior belief); `supersede` replaces a value. Among contradictory *believed* facts,
`resolve_current` ranks by (source trust, confidence, recency) — trust and confidence stay separate
dimensions (mission §15).

## Consequences
- The four-corner queries in mission §10 (CASO1/CASO2) are tested and pass.
- Half-open semantics are pinned by a boundary test (surfaced by mutation testing).
- Callers must choose `supersede` vs `correct_validity` deliberately; both are documented.

## Rejected alternatives
- **Uni-temporal (tx time only)** (Mem0/Letta): cannot represent "true in the past, learned now";
  painful to retrofit. Rejected.
- **Whole-DB snapshot versioning** (Dolt): wrong altitude for per-entity belief. Rejected.
- **Blend trust+confidence into one scalar**: violates §15; kept as ordered tuple components.
