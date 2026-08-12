# EPISTEMOS v0.5 — Final Report (EPISTEMOS-05: Collaborative Claims)

**Repo:** `Voltolini-SPACE/epistemos` · **Branch:** `feat/epistemos-05-collaborative-claims` · **Tag:**
`epistemos-v0.5.0` (v0.1.0–v0.4.0 unchanged) · **Python:** 3.14.5 · **Runtime deps:** 0 ·
**License:** MIT.

## Executive summary

EPISTEMOS-05 turns Knowledge Spaces into **verifiable collaborative epistemology**. The governing
principle is one line: **CONTRIBUTION ≠ TRUTH.** The system can now answer *what has been claimed,
by whom, on what evidence, what contradicts it, who reviewed it, what we believe, why, what changed
that belief, and what remains disputed* — without a submission becoming truth by being submitted,
and without a majority standing in for verification. No network, federation, or LLM is shipped; the
core stays sovereign, local-first, zero-egress.

- **Claim graph, not an overloaded Fact (ADR-028).** `Claim`, `Evidence`, `Review` are new object
  kinds that reuse `Envelope` + the hash-chained ledger + bitemporal helpers + the v0.4 spaces
  firewall + `explain`. A Claim *exists* independent of belief; Evidence attaches with a **typed**
  relation (supports/contradicts/weakens/derived_from); Reviews are **individual and preserved**.
- **Belief is derived, never stored (ADR-029).** `derive_belief` computes
  PROPOSED/SUPPORTED/DISPUTED/ACCEPTED/REJECTED/RETRACTED/SUPERSEDED with a `why`. One live dispute
  ⟶ DISPUTED against any number of confirmations (**majority is not truth**). A governed acceptance
  dominates but **records the coexisting dispute** rather than erasing it.
- **Acceptance is governed through a policy port (ADR-029).** `knowledge.accept` is a **non-default**
  capability, enforced **in the engine before** a pluggable `Policy` runs (so a lenient policy can't
  bypass it). The default `LocalDefaultPolicy` is deterministic and offline; NOMOS or a quorum policy
  plugs in via `Engine(store, policy=…)` — a plug, never a dependency. A claimant **cannot** accept
  their own claim (self-review is allowed but disclosed; self-*acceptance* is denied).
- **Four separate identities kept separate (§3):** `owner` (ingesting agent) ≠ `claimant` (asserter)
  ≠ `source` (external origin) ≠ reviewer (a Review's owner).
- **P0 leak invariants held under the adversarial battery:**
  `CLAIM_SPACE_LEAK = EVIDENCE_SPACE_LEAK = REVIEW_SPACE_LEAK = PRIVATE_TO_PUBLIC_LEAK = 0`.

**Verification:** 855 tests (memory+SQLite parity), `mypy --strict` clean (32 files), ruff clean,
targeted mutation **39/39 killed (0 non-equivalent survived)**, 30-cycle race, crash-recovery chaos,
zero-egress trap intact. Baselines v0.1–v0.4 unmoved.

## The four mandated questions (answered with adversarial evidence)

### Q1 — Can two agents make competing claims about the same thing, and can the system represent them without declaring a winner by submission?

**Yes.** Two agents asserting the same or opposite propositions produce **two distinct claims**, each
with its own `claimant`, evidence, reviews and derived belief — the engine never merges or
deduplicates them (`test_two_agents_asserting_the_same_thing_are_two_claims_not_one`; corroboration ≠
dedup). Neither is "true" by existing: a bare claim is `PROPOSED`, and even a claimant self-confirming
reaches only `SUPPORTED`, never `ACCEPTED`
(`test_a_contributor_cannot_make_a_claim_true_by_asserting_it`). A single dispute holds belief at
`DISPUTED` regardless of confirmation count (mutation `belief_dispute_ignored`, killed). Truth is only
ever produced by a **governed** act gated on `knowledge.accept`, which the claimant themselves cannot
perform (`test_claimant_with_the_accept_capability_still_cannot_self_accept`).

### Q2 — Can agents share evidence for collaborative verification without leaking restricted knowledge?

**Yes, with composition proven.** Evidence is a first-class, space-scoped object; a claim and the
objects behind it can carry **different** visibilities. `claim_evidence`/`explain_claim` re-authorize
each referenced object **individually** against the caller, so a broadly-visible claim never
transitively exposes private evidence: `test_public_claim_does_not_expose_private_evidence` shows an
ORG-visible claim whose private supporting memo is returned to its owner and **elided (empty list)**
for everyone else. You cannot attach evidence you cannot read (`test_attach_requires_read_of_both_sides`),
reviews are invisible outside the claim's space (`REVIEW_SPACE_LEAK=0`), and belief is derived over
**only readable reviews**. Mutation `claim_evidence_readability_removed` (which would leak private
evidence through a public claim) is **killed**.

### Q3 — Can the system explain *why* it believes (or disputes) something, auditably?

**Yes.** Belief is never a stored boolean — it is derived by a pure function and carries a `why` plus
the contributing reviews. `explain_claim` returns the full genealogy — statement, claimant vs
ingesting agent vs source, typed evidence, each individual review (with `self_review` disclosed),
contradictions, derived belief + `why`, space, and bitemporal status — with **authorization applied
before traversal**, so unreadable nodes are elided, never exposed (the v0.4 `explain` ancestor-leak
stays permanently closed). Crucially, a governed acceptance is auditable *as an override*: an accepted
claim that still has a dispute on record reports `"NOTE: N dispute/reject still on record"` (mutation
`belief_governance_hides_dispute`, killed). The decision and the disagreement it overruled are both
visible.

### Q4 — Can the entire collaborative state be reconstructed from the ledger alone?

**Yes.** Every claim, evidence link, review, and governance act is an append-only, hash-chained
ledger event; nothing is written to the store outside the ledger. `rebuild_projection` reproduces the
claim graph exactly, including an accepted-with-coexisting-dispute claim
(`test_rebuild_projection_equals_replay_with_claims`, `test_collaborative_state_rebuilds_from_ledger_alone`).
After a simulated crash, a fresh engine reconstructs belief, evidence, governance and the space
firewall from the ledger alone, with no private-claim leak on recovery, and governance is atomic —
recovery sees a claim as accepted or not, never half-accepted. Tampering with any claim/review/
acceptance payload breaks the chain (`test_claim_ledger_is_tamper_evident`).

## Scope discipline

- **No universal trust score.** Claimant/source/reviewer trust are different questions and stay
  separate; cross-dimension reputation is **EPISTEMOS-07**, explicitly out of scope (ADR-028).
- **No network/federation.** The policy port is offline; nothing in v0.5 opens a socket. Federated
  claim exchange remains future work.
- **NOMOS/Hermes/OpenClaw untouched.** Governance is delegated through a `Policy` callable injected
  by the host — the core does not import or depend on any of them.

## Gate matrix

See [`docs/STATUS.md`](STATUS.md) → *EPISTEMOS-05 (COLLABORATIVE CLAIMS) gates*.
`STATUS_FINAL = EPISTEMOS_V0_5_PASS`.

## Reproduce

```bash
python -m pytest tests -q                                   # 855 passed
python -m mypy --strict src/epistemos                        # clean (32 files)
python -m ruff check src tests benchmarks                    # clean
python tools/mutation_harness.py                             # 39/39 killed, 0 survived
python benchmarks/bench.py --scales 1000 10000               # core unchanged; claim ops reported
```
