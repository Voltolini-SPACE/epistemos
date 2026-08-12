# Contradiction & dispute model

EPISTEMOS represents disagreement **explicitly and durably**. Contradiction is never resolved by
deletion, averaging, or out-voting; competing positions coexist and are all inspectable.

## Three ways disagreement is recorded

1. **Contradicting evidence** — `attach_evidence(..., relation="contradicts" | "weakens")` links a
   typed counter-artifact to a claim. The relation is preserved verbatim; contradicting evidence is
   never silently upgraded to supporting (mutation `claim_review_space_inherit_removed` and the
   adversarial `test_contradicting_evidence_is_preserved_as_contradiction` guard the path).
2. **Disputing reviews** — a `dispute`/`reject` verdict from any reviewer. A single live dispute
   makes belief `DISPUTED` regardless of how many confirmations exist (**majority is not truth**, §9).
3. **Competing claims** — two agents may assert contradictory propositions. They are **two claims**
   (corroboration/competition ≠ dedup), each with its own `claimant`, evidence, reviews and derived
   belief. The engine does not merge them.

## What "disputed" means and how it clears

`DISPUTED` is a first-class belief state, not an error. It clears only when:

- the disputing reviews are themselves superseded by newer assessments that no longer dispute, **or**
- a **governed acceptance/rejection** is recorded (`knowledge.accept`). Even then, governance does
  **not erase** the dispute: an accepted claim's `why` still notes "N dispute/reject still on record"
  (§10). The audit trail shows both the decision and the disagreement it overrode.

## Nothing is destroyed

Retraction and supersession are append-only and first-close-wins; reviews and evidence are immutable
events. The complete history of a contested statement — who claimed it, who disputed it, what
evidence contradicts it, who accepted it and over which objections — is reconstructable by replaying
the ledger. See `BELIEF_MODEL.md`, `ADR-028`, `ADR-029`.
