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

## EPISTEMOS-03 hardening & known residual

- **A belief closes exactly once (A-12).** `supersede`/`retract`/`correct_validity` refuse an
  already-closed belief (`ConflictError`), and the projection keeps the *earliest* `tx_to`, so
  transaction time is genuinely append-only: `as_of(at_tx=T)` cannot change its answer about a past
  instant, and no import/rebuild can move a close forward. Pinned by `test_belief_close_once.py` and
  mutants `core_open_belief_guard` / `core_belief_reclose`.
- **"Believed now" is clock-independent (T-05/T-06).** The belief predicate for `current`,
  `as_of(default now)` and `search(believed_only)` is *the interval is open* (`tx_to is None`), not a
  comparison against a clock instant — so queries do not depend on how the engine clock relates to the
  data's timestamps (important for imported/federated data stamped by another clock). An explicit
  `at_tx=T` still anchors on T. See `temporal.believed()`.
- **KNOWN RESIDUAL (T-03, deferred to EPISTEMOS-05).** `confirm()` mutates a fact's `confidence`
  **in place** (it is a corroboration annotation, not a new generation), so a later confirmation
  changes the confidence a historical `as_of()` would report. Confidence is therefore *not* yet
  bitemporally versioned. The EPISTEMOS-03 `delta ≥ 0` fix (B-03) removes the ability to weaponize
  this cross-agent; making confidence generational is future work.

## Rejected alternatives
- **Uni-temporal (tx time only)** (Mem0/Letta): cannot represent "true in the past, learned now";
  painful to retrofit. Rejected.
- **Whole-DB snapshot versioning** (Dolt): wrong altitude for per-entity belief. Rejected.
- **Blend trust+confidence into one scalar**: violates §15; kept as ordered tuple components.
