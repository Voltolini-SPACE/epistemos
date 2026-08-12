# Claim graph threat model (EPISTEMOS-05)

Adversary: an authenticated principal (or a compromised agent) inside a tenant, trying to
manufacture truth, leak restricted material, or corrupt the collaborative record. The MCP/network
boundary is hostile; the core is local-first, zero-egress, no LLM.

| # | Attack | Defense | Verified by |
|---|--------|---------|-------------|
| 1 | **Truth by submission** — assert a claim and have it believed | belief is *derived*; a bare claim is `PROPOSED`; even self-confirm only reaches `SUPPORTED` | `test_a_contributor_cannot_make_a_claim_true…`; `belief_dispute_ignored` |
| 2 | **Truth by majority** — pile on confirmations to bury a dispute | one live dispute ⟶ `DISPUTED`; belief is not a tally | `test_dispute_makes_it_disputed…`; mutation `belief_dispute_ignored` |
| 3 | **Self-acceptance** — claimant governs own claim into `ACCEPTED` | `_govern` denies claimant == principal (§32) | `test_claimant…cannot_self_accept`; mutation `claim_self_acceptance_removed` |
| 4 | **Capability escalation** — accept without the truth gate | `knowledge.accept` is non-default and enforced **in the engine before the policy** | `test_a_default_agent_cannot_accept…`, `…under_a_permissive_policy`; mutation `claim_accept_cap_removed` |
| 5 | **Lenient-policy bypass** — install an allow-all policy | engine's own `require(knowledge.accept)` runs first | `test_engine_enforces_accept_capability_even_under_a_permissive_policy` |
| 6 | **Claim-space leak** — read a claim outside your spaces | space firewall; `NotFoundError` (no oracle) on belief/explain | `test_private_claim_is_invisible…`; mutation `claim_ref_readable_oracle` |
| 7 | **Evidence leak via a public claim** — see private evidence behind a visible claim | `claim_evidence`/`explain_claim` filter by evidence readability (§15) | `test_public_claim_does_not_expose_private_evidence`; mutation `claim_evidence_readability_removed` |
| 8 | **Review leak** — observe a restricted review / infer it in belief | reviews inherit the claim's spaces; belief over readable reviews only | `test_review_is_invisible_outside…`; mutation `claim_review_space_inherit_removed` |
| 9 | **Existence oracle** — distinguish hidden-real from absent | both return `None`/`NotFoundError` identically | `test_no_existence_oracle_across_the_space_boundary` |
| 10 | **Cross-tenant** — read/govern another tenant's claim | tenant is the hard boundary; scope check | `test_claims_never_cross_a_tenant_boundary` |
| 11 | **Attach across a boundary** — link evidence you can't see | attach requires read of both sides | `test_attach_requires_read_of_both_sides` |
| 12 | **Forged evidence relation** — pass contradicting evidence as support | relation preserved verbatim | `test_contradicting_evidence_is_preserved…` |
| 13 | **Corroboration collapse** — dedup competing claims into one | claims are never merged; each keeps its claimant | `test_two_agents_asserting_the_same_thing…` |
| 14 | **Ledger tamper** — edit a claim/review/acceptance payload | hash-chained ledger; `verify_chain` fails closed | `test_claim_ledger_is_tamper_evident` |
| 15 | **Crash mid-acceptance** — leave a half-accepted claim | governance is a single atomic ledger event; recovery sees accepted or not | `test_collaborative_state_rebuilds_from_ledger_alone` |
| 16 | **Belief drift on rebuild** — projection disagrees with replay | `rebuild_projection == replay` incl. claims | `test_rebuild_projection_equals_replay_with_claims` |

**Residual / out of scope:** cross-dimension reputation and weighting of claimants/reviewers is
**EPISTEMOS-07** (deliberately not built here — a universal `trust_score` was rejected, ADR-028).
Federation/network sharing of claims remains future work; nothing in v0.5 opens a socket.

Coverage: 39/39 targeted mutants killed (`docs/security/MUTATION_REPORT.md`), 30-cycle race and
crash-recovery chaos suites green, full suite 855 tests, `mypy --strict` clean, zero-egress trap
intact.
