# EPISTEMOS v0.4 — Final Report (EPISTEMOS-04: Knowledge Spaces & Capability Model)

**Repo:** `Voltolini-SPACE/epistemos` · **Branch:** `feat/epistemos-04-knowledge-spaces` · **Tag:**
`epistemos-v0.4.0` (v0.1.0/v0.2.0/v0.3.0 unchanged) · **Python:** 3.14.5 · **Runtime deps:** 0 ·
**License:** MIT.

## Executive summary

EPISTEMOS-04 builds the fundamental boundaries for future collaboration **without** shipping a
network, federation, or public community: Knowledge Spaces (a visibility lattice orthogonal to
tenant), capability-based authorization, explicit sharing/promotion with preserved lineage, and an
absolute guard against accidental `PRIVATE → PUBLIC` flow. The v0.3 baseline stays intact; the
license moves to MIT.

- **Model:** `Visibility` lattice `PRIVATE<TEAM<ORGANIZATION<COMMUNITY<PUBLIC`; a `KnowledgeSpace`
  per tenant; every object carries `spaces` (empty = PRIVATE to owner, the fail-closed default).
- **Authorization firewall** `IDENTITY→TENANT→SPACE→CAPABILITY→POLICY`, applied
  **candidate-boundary-first** on every read surface (get/search/current/as_of/timeline/facts_for/
  recall/explain/graph/export) so an unauthorized object cannot leak via content, score, rank, count,
  or ranking-timing. Grants are server-side (projected from ledger events), never client claims.
- **Capabilities, not roles:** roles are documented capability sets; enforcement is always by
  capability. `knowledge.share`/`knowledge.promote` are NOT default — no default principal can move
  knowledge toward PUBLIC. Promotion to ORG+ requires `knowledge.promote`, the single gate to PUBLIC.
- **P0 held:** `PRIVATE_TO_PUBLIC_LEAK = 0` under the full adversarial battery (§11/§27). One real
  leak was found by the battery during development — `explain()` exposed a private ancestor of a
  shared object — and fixed (genealogy now elides unreadable nodes) before it could ship.

## The direct question

> *Can a user safely share selected EPISTEMOS knowledge with another user or group without exposing
> the remainder of their private knowledge?*

**YES** — supported by adversarial evidence, not intention. A user creates a space, grants specific
agents, and `share`s specific objects; everything else stays PRIVATE. The adversarial battery proves
the remainder is observable through no surface (get, search on index **and** scan fallback,
current/as_of, timeline, facts_for, recall, explain/provenance, graph traversal, scoped export,
crafted import), across capability revocation, forged-membership, crash-recovery, and index
corruption. Mutation testing (32/32 killed, 0 survived) covers the boundary predicates; the
`spaces_*` mutants each reopen a specific leak and are all caught.

## Gate matrix

Full matrix: `docs/STATUS.md` (EPISTEMOS-04 section). Headline gates:

| Gate | Status | Evidence |
|------|--------|----------|
| KNOWLEDGE_SPACES | PASS | ADR-024; `test_spaces_model.py` |
| CAPABILITY_ENFORCEMENT | PASS | ADR-025; `test_capability_model.py`, `test_authz_unit.py` |
| PRIVATE_DEFAULT | PASS | fail-closed `spaces == ()`; `test_spaces_model.py` |
| PRIVATE_TO_PUBLIC_LEAK = 0 | PASS | `test_private_public_invariant.py` |
| AUTHORIZED_RETRIEVAL | PASS | ADR-026; candidate-boundary-first, score/count non-leak |
| FTS/GRAPH/PROVENANCE/EXPORT SPACE_ISOLATION | PASS | `test_space_export_graph.py`, explain elision |
| RACE (30 cycles) / CHAOS | PASS | `test_space_race.py`, `test_space_chaos.py` |
| MUTATION_NON_EQUIVALENT_SURVIVED = 0 | PASS | 32/32 killed |
| BACKWARD_COMPATIBILITY | PASS | `test_backward_compat.py` (legacy → PRIVATE) |
| ZERO_EGRESS / LOCAL_FIRST | PASS | freeze proof, 0 socket ops full lifecycle |
| MIT_LICENSE_MIGRATION | PASS | ADR-027; APACHE_REFERENCE_RESIDUAL=0 |

Tests: **780 passed**, ruff + mypy `--strict` clean, mutation **32/32 killed / 0 survived**.

## Backward compatibility

A v0.3 database (objects without `spaces`) projects to fully-PRIVATE; single-agent behaviour is
byte-identical; `rebuild_projection == replay` holds. The one intentional change is the B-02
correction: within a namespace, an object is private to its owner by default, and cross-agent access
now requires an explicit `share` — the v0.3 tests that relied on implicit shared-namespace reads were
rewritten to the spaces model (documented in ADR-024).

## Performance (measured, §31)

`docs/benchmarks/EPISTEMOS_04_AUTHZ_BENCHMARK.md`: the firewall adds an O(matched-candidates)
authorization filter — common-term search ≈1.6× at 100k; rare-term search, `current`, `as_of`, `get`
unchanged; ORG-corpus writes ≈1.5× (promotion events). No security check was weakened for a number.

## Licensing (MIT migration)

`LICENSE` = verbatim MIT, (c) 2026 Voltolini (voltolini.space); `pyproject` metadata, README,
CONTRIBUTING, brand/security docs = MIT (ADR-027). Provenance audit: zero runtime deps + clean-room
⇒ nothing blocks MIT; third-party facts and required notices preserved. Git history not rewritten.

## Known gaps (honest, non-blocking, deferred)

- **Per-space FTS partitioning** — the FTS MATCH resolves over the whole namespace before the space
  predicate, so search *latency* couples across spaces within a namespace (the OV-04 coupling, one
  level up). No content/score/count leak; timing isolation is the follow-up hardening.
- **Claim graph / generational confidence / contributor reputation** — EPISTEMOS-05 (the claim-review
  pipeline; T-03's confidence-not-versioned residual stays open).
- **Federation / packages / network** — EPISTEMOS-06+, explicitly out of scope here (§35).

## External isolation

NOMOS `~/Desktop/NOMOS_REPO/nomos` HEAD `2cea197e` + 2 pre-existing dirty (untouched);
`~/.hermes/config.yaml` and `~/.openclaw/openclaw.json` SHA-256 identical to baseline.

## Final status block

```
STATUS_FINAL = EPISTEMOS_V0_4_PASS
VERSION = 0.4.0   HEAD = <freeze commit>   TAG = epistemos-v0.4.0
TESTS = 780 passed / 0 failed   MUTATION = 32/32 killed, 0 survived
RACE = PASS   CHAOS = PASS
KNOWLEDGE_SPACES = PASS   CAPABILITY_MODEL = PASS   PRIVATE_DEFAULT = PASS
PRIVATE_TO_PUBLIC_LEAK = 0   AUTHORIZED_RETRIEVAL = PASS
BACKWARD_COMPATIBILITY = PASS   ZERO_EGRESS = PASS   LOCAL_FIRST = PASS
MIT_LICENSE_MIGRATION = PASS   APACHE_REFERENCE_RESIDUAL = 0   LICENSE_CONTRADICTION = 0
NOMOS_UNTOUCHED = TRUE   HERMES_UNTOUCHED = TRUE   OPENCLAW_UNTOUCHED = TRUE
```
