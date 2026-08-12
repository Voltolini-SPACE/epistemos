# Knowledge Spaces Threat Model (EPISTEMOS-04, SHIPPED)

Scope: the boundaries added by Knowledge Spaces (visibility + capability). The single-instance
model (`docs/security/THREAT_MODEL.md`, S1–S50: tenant isolation, ledger tamper, inert ingestion,
zero-egress) is inherited unchanged and referenced, not duplicated. Federation is out of scope
(EPISTEMOS-06); this mission adds visibility and authorization within one instance.

## Trust boundaries added

```
  Space edge (PRIVATE ↔ shared)  — crossed ONLY by an explicit, authorized, logged share/promote.
  Contributor ↔ space            — a contributor is attributable but NOT authoritative;
                                    confirming/disputing a fact requires reading it.
```

## Threats and mitigations (all shipped + tested)

| # | Threat | Mitigation | Evidence |
|---|--------|------------|----------|
| K1 | implicit PRIVATE→PUBLIC flow | single gated placement path; PRIVATE default; promote cap not default | `test_private_public_invariant.py`; mutant `spaces_promote_cap_removed` |
| K2 | cross-space read via retrieval (score/count/timing of ranking) | candidate-boundary-first firewall; unauthorized dropped before scoring | `test_search_score_and_count_do_not_leak`; mutant `spaces_search_authorize_removed` |
| K3 | fallback (scan) leakage | scan enforces identical predicate | `test_degraded_index_fallback_does_not_leak` |
| K4 | FTS space leakage / crafted space ids | tenant/namespace filter at SQL; space predicate over candidates; dangling id → no access | `test_import_into_empty_store_does_not_grant_foreign_space` |
| K5 | graph node/edge leakage | edge visible only if relation AND far endpoint readable | `test_graph_traversal_does_not_leak_private_node` |
| K6 | provenance/explain leakage | unreadable genealogy nodes elided | `test_cross_space_id_reference_does_not_leak` |
| K7 | export leakage | scoped export = only readable objects' events | `test_scoped_export_excludes_unreadable_objects` |
| K8 | crafted import scope rewrite | sealed-header scope authority (A-01) | `test_crafted_import_cannot_downgrade_visibility` |
| K9 | capability escalation via forged Principal | membership is server-side projected state | `test_client_cannot_forge_membership_via_principal`; mutant `spaces_member_check_removed` |
| K10 | stale capability replay | revoke denies immediately; no token trust | `test_stale_capability_after_revoke_denies`; mutant `spaces_grant_active_ignored` |
| K11 | visibility downgrade/upgrade | promotion is monotone; downgrade refused; append-only | `promote` monotone check |
| K12 | promotion replay / double promotion | idempotent placement; rebuild-stable | `test_promotion_survives_rebuild` |
| K13 | cross-tenant / cross-namespace / principal confusion | fail-closed decision branches | `test_authz_unit.py`; mutant `spaces_deny_to_allow` |
| K14 | index corruption → leak | verify detects drift → DEGRADED → scan; no leak | `test_index_corruption_does_not_leak_private` |
| K15 | blind cross-space mutation (confirm/contradict) | requires read access to the target | `test_cannot_confirm_a_fact_you_cannot_see` |

## Gates

`SPACE_ISOLATION=PASS` · `CAPABILITY_ENFORCEMENT=PASS` · `PRIVATE_DEFAULT=PASS` ·
`PRIVATE_TO_PUBLIC_LEAK=0` · `AUTHORIZED_RETRIEVAL=PASS` · `FTS/GRAPH/PROVENANCE_SPACE_ISOLATION=PASS`
· `EXPORT_IMPORT_SPACE_SAFETY=PASS` · `RACE=PASS` · `CHAOS=PASS` · `MUTATION_NON_EQUIVALENT_SURVIVED=0`
· `ZERO_EGRESS=PASS` · `LOCAL_FIRST=PASS`.

## Out of scope this mission (mission §35, deferred)

Federation/network, subscriptions, global reputation, social ranking, marketplace, central identity,
mandatory cloud, auto-sync — EPISTEMOS-05/06/07. Per-space FTS partitioning (timing isolation) is the
one documented hardening follow-up.
