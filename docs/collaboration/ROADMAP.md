# EPISTEMOS — Collaborative / Federated Roadmap

> **Status: PLAN — DEFERRED.** Nothing here ships in v0.3. This is the sequencing of the
> collaborative vision assessed in [`COLLABORATIVE_KNOWLEDGE_MODEL.md`](COLLABORATIVE_KNOWLEDGE_MODEL.md).
> The addendum's proposed decomposition is adopted; where the audit found a technically superior
> ordering it is noted. Each milestone is a *designed, adversarially-testable* step with no
> irreversible decision taken prematurely (addendum §28).

## Sequencing rationale

Nothing can be shared safely until **visibility** and **authorization** are first-class and
fail-closed — so Knowledge Spaces + the capability model come first. Everything else is built on
that boundary. This ordering also front-loads the one architectural gap the audit found (B-02:
namespace is a partition, not an authorization boundary).

| Milestone | Theme | Delivers | Depends on |
|-----------|-------|----------|------------|
| **EPISTEMOS-03** (done) | Audit + uplift | The leak fixes (A-01, A-11, B-06, B-01), append-only tx-time (A-12), retrieval parity (ADR-021), provenance index (ADR-022), unicode search (ADR-023). *The collaborative foundation, delivered as current-defect work.* | — |
| **EPISTEMOS-04** | Knowledge Spaces + Capability model | `space`/`visibility` first-class + fail-closed PRIVATE default; capability-based enforcement (roles = capability sets); the `PRIVATE→PUBLIC` leak invariant + tests; per-space index partitioning (OV-04); observability/metrics. | 03 |
| **EPISTEMOS-05** | Collaborative claims | Contributor identity (distinct from owner/principal/source); claim graph + review pipeline; generational confidence (closes T-03); per-domain reputation as evaluation *input*; phrase/field search; bulk ingest; pagination. | 04 |
| **EPISTEMOS-06** | Knowledge Packages + Federation | Signed package (scoped export + manifest, standard crypto); peer/central federation behind one port; subscriptions; offline revocation; PROV-O/PROV-JSON export; ledger snapshot/compaction. | 04, 05 |
| **EPISTEMOS-07** | Federated security | Sybil resistance, coordinated-confirmation caps, reputation-farming/evidence-laundering/replay defenses. | 06 |
| *(only then)* | Public collaborative network | — | 07 |

## Gates each milestone must pass before freeze (from the threat model)

- **04:** `VISIBILITY_DEFAULT=PRIVATE`, `CROSS_SPACE_RETRIEVAL_LEAK=0`, `PRIVATE_TO_PUBLIC_LEAK=0`,
  `PROMOTION_FAIL_CLOSED=TRUE`, plus the standing `STANDALONE_WITHOUT_NETWORK` / `ZERO_EGRESS_DEFAULT`.
- **05:** `CLAIM_NOT_TRUTH=TRUE`, `DIMENSIONS_SEPARATE=4`, `REPUTATION_IS_INPUT_NOT_AUTHORITY=TRUE`.
- **06:** `FEDERATION_REPLAY_BLOCKED=TRUE`, `STANDARD_CRYPTO_ONLY=TRUE`,
  `NO_MANDATORY_CENTRAL_AUTHORITY=TRUE`, `INGESTED_CONTENT_INERT=TRUE` (restated for packages).
- **07:** Sybil/poisoning gates from `THREAT_MODEL.md` §4.

## Invariants that never regress across the whole roadmap

Local-first, zero-egress-by-default, PRIVATE-by-default/fail-closed, claim≠truth, the four separate
trust dimensions, tamper-evident append-only ledger, bitemporal immutability of the past,
storage-agnosticism, and no mandatory central authority. Any milestone that would sacrifice one of
these is a `REJECTED_DIRECTION`.

See the companion designs: [`KNOWLEDGE_SPACES.md`](KNOWLEDGE_SPACES.md),
[`CLAIMS_EVIDENCE_TRUST.md`](CLAIMS_EVIDENCE_TRUST.md),
[`FEDERATION_ARCHITECTURE.md`](FEDERATION_ARCHITECTURE.md),
[`KNOWLEDGE_PACKAGE_SPEC.md`](KNOWLEDGE_PACKAGE_SPEC.md), [`THREAT_MODEL.md`](THREAT_MODEL.md).
