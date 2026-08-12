# EPISTEMOS Mutation Report (targeted critical-boundary harness)

Method: per-mutant, copy the package, apply one source mutation, run the invariant
suite against the copy, classify by pytest **exit code** (mission §32). Reproduce:
`python tools/mutation_harness.py`.

- CONTROL (unmutated copy) pytest rc = 0 (0 = green baseline)
- Every mutant below is **non-equivalent by construction** (it changes a load-
  bearing predicate), so the target is `SURVIVED == 0`.

```
MUTANTS_TOTAL              = 39
MUTANTS_NON_EQUIVALENT     = 39   (all curated mutants change behavior)
MUTANTS_KILLED            = 39
MUTANTS_SURVIVED          = 0
INVALID_MUTATIONS         = 0
CRITICAL_NON_EQUIVALENT_SURVIVED = 0
```

| mutant | boundary | result | detail | protects |
|--------|----------|--------|--------|----------|
| `temporal_lower_ge_to_gt` | temporal | **KILLED** | pytest rc=1 | valid-time lower bound inclusion |
| `temporal_upper_lt_to_le` | temporal | **KILLED** | pytest rc=1 | valid-time upper bound exclusion (half-open) |
| `ledger_skip_content_hash` | ledger | **KILLED** | pytest rc=1 | payload tamper detection |
| `ledger_skip_prev_link` | ledger | **KILLED** | pytest rc=1 | chain-break detection |
| `ledger_skip_seq_check` | ledger | **KILLED** | pytest rc=1 | reorder/removal/duplicate detection |
| `model_skip_confidence_bound` | validation | **KILLED** | pytest rc=1 | confidence [0,1] bound |
| `model_skip_valid_interval` | temporal | **KILLED** | pytest rc=1 | valid_to >= valid_from |
| `identity_skip_name_regex` | identity | **KILLED** | pytest rc=1 | namespace/tenant identifier validation (unicode confusables) |
| `identity_skip_owner_guard` | agent-isolation | **KILLED** | pytest rc=1 | cross-agent write (owner) guard |
| `core_skip_ref_scope` | tenant-isolation | **KILLED** | pytest rc=1 | cross-tenant reference scope check |
| `core_supersede_no_close` | supersession | **KILLED** | pytest rc=1 | supersede must close old belief |
| `core_import_no_verify` | import | **KILLED** | pytest rc=1 | import chain verification on tamper |
| `idx_search_tenant_leak` | index-tenant | **KILLED** | pytest rc=1 | FTS query tenant filter (cross-tenant leak) |
| `idx_temporal_and_to_or` | index-temporal | **KILLED** | pytest rc=1 | temporal component = believed AND valid |
| `idx_persist_skip_reindex` | index-consistency | **KILLED** | pytest rc=1 | writes must update the index |
| `idx_verify_always_true` | index-consistency | **KILLED** | pytest rc=1 | verify detects index drift/corruption |
| `idx_fallback_inverted` | index-fallback | **KILLED** | pytest rc=1 | use index only when HEALTHY else fall back |
| `idx_lexical_zeroed` | index-scoring | **KILLED** | pytest rc=1 | lexical score contribution to explainability |
| `core_import_scope_authority` | tenant-isolation | **KILLED** | pytest rc=1 | ledger header is the sole scope authority on import (A-01) |
| `core_belief_reclose` | bitemporal | **KILLED** | pytest rc=1 | projection keeps the earliest belief close (A-12) |
| `core_open_belief_guard` | bitemporal | **KILLED** | pytest rc=1 | refuse to re-close an already-closed belief (A-12) |
| `core_confirm_negative_delta` | agent-isolation | **KILLED** | pytest rc=1 | confirm only corroborates, never lowers confidence (B-03) |
| `retrieval_source_scope` | tenant-isolation | **KILLED** | pytest rc=1 | source is never dereferenced across scope (B-06) |
| `idx_verify_content_drift` | index-consistency | **KILLED** | pytest rc=1 | verify detects FTS content-cell corruption (B-01) |
| `rest_none_principal` | auth-fail-closed | **KILLED** | pytest rc=1 | REST refuses a non-Principal from the auth resolver (B-01) |
| `spaces_private_default_to_public` | spaces-fail-closed | **KILLED** | pytest rc=1 | absent visibility defaults PRIVATE, never PUBLIC (§5) |
| `spaces_deny_to_allow` | space-tenant | **KILLED** | pytest rc=1 | read decision fails closed on tenant mismatch |
| `spaces_owner_check_removed` | space-private | **KILLED** | pytest rc=1 | a private object is readable only by its owner |
| `spaces_member_check_removed` | space-membership | **KILLED** | pytest rc=1 | TEAM access requires ownership or a granted membership |
| `spaces_promote_cap_removed` | space-promote | **KILLED** | pytest rc=1 | promotion to ORG+ requires the knowledge.promote capability (§11) |
| `spaces_search_authorize_removed` | space-retrieval | **KILLED** | pytest rc=1 | unauthorized candidates dropped before scoring (§12) |
| `spaces_grant_active_ignored` | space-revocation | **KILLED** | pytest rc=1 | a revoked (inactive) grant denies access (§22) |
| `claim_self_acceptance_removed` | claim-governance | **KILLED** | pytest rc=1 | a claimant cannot govern their own claim into truth (§32) |
| `claim_accept_cap_removed` | claim-truth-gate | **KILLED** | pytest rc=1 | acceptance requires the non-default knowledge.accept capability |
| `claim_evidence_readability_removed` | visibility-composition | **KILLED** | pytest rc=1 | a public claim never exposes private evidence (§15) |
| `claim_ref_readable_oracle` | claim-firewall | **KILLED** | pytest rc=1 | a claim outside the caller's spaces is invisible (no oracle §17) |
| `claim_review_space_inherit_removed` | review-leak | **KILLED** | pytest rc=1 | a review inherits the claim's audience (REVIEW_SPACE_LEAK=0) |
| `belief_dispute_ignored` | belief-derivation | **KILLED** | pytest rc=1 | one live dispute makes belief DISPUTED — majority is not truth (§9) |
| `belief_governance_hides_dispute` | belief-audit | **KILLED** | pytest rc=1 | governed acceptance still records a coexisting dispute (§10) |

**MUTATION_CRITICAL = PASS**

