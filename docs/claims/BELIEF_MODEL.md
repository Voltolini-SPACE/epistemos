# Belief model

Belief is a **derived, explainable state — never a stored boolean** (§10). No code path can "set
believed = true"; belief is only ever *computed* from the ledger-projected claim, its readable
reviews, and any governed acceptance/rejection. `derive_belief` is a pure function
(`claims/belief.py`); `Engine.belief(...)` and `explain_claim(...)` expose it.

## States

`proposed` · `supported` · `disputed` · `accepted` · `rejected` · `retracted` · `superseded`

## Derivation (precedence, highest first)

1. **Lifecycle** — a `retracted`/`superseded` claim short-circuits to `RETRACTED`/`SUPERSEDED`.
2. **Governance** — a governed `rejected` ⟶ `REJECTED`; a governed `accepted` ⟶ `ACCEPTED`.
3. **Review picture** — any live `dispute`/`reject` ⟶ `DISPUTED`; else confirmations ⟶ `SUPPORTED`;
   else ⟶ `PROPOSED`.

Every result carries a `why` string and the list of contributing reviews, so belief is auditable.

## Two invariants that keep belief honest

- **Majority is not truth (§9).** One live dispute makes a claim `DISPUTED` even against many
  confirmations. Belief is not a vote tally. (Mutation `belief_dispute_ignored` guards this.)
- **Governance dominates but does not erase (§10).** A governed acceptance sets `ACCEPTED`, and the
  `why` *still records the coexisting dispute* ("NOTE: N dispute/reject still on record"). An
  override is visible as an override. (Mutation `belief_governance_hides_dispute` guards this.)

## Belief is computed over what the caller may read

`belief()` derives from `_readable_reviews` — reviews outside the caller's spaces do not contribute
to (and cannot be inferred from) their answer. Two members of the same space get the same belief; a
non-member gets `NotFoundError`, not a partial belief.

## Governed acceptance (not a vote)

`accept_claim` / `reject_claim`:

- require the **`knowledge.accept`** capability — a **non-default** right (ordinary contribution and
  review are default; the truth gate is not). The engine enforces this **before** consulting the
  policy, so it cannot be bypassed by installing a lenient policy.
- **deny self-acceptance**: a claimant cannot govern their own claim (§32).
- delegate the decision to a pluggable **policy port** (`Policy`). The default `LocalDefaultPolicy`
  is deterministic, offline, threshold-free; a deployment can inject NOMOS or a quorum policy via
  `Engine(store, policy=…)` without the core depending on it.

Governed acceptance and rejection are ledger events (`CLAIM_ACCEPTED`/`CLAIM_REJECTED`); rebuilding
the projection reproduces belief exactly, including accepted-with-coexisting-dispute. See `ADR-029`.
