# ADR-028 — Collaborative claims: a claim graph distinct from the knowledge graph

**Status:** Accepted (v0.5)

## Context

Through v0.4 EPISTEMOS answered *"what do we know, and who may see it?"* A `Fact` is a **believed**
statement in the knowledge graph; confirmation raised its confidence, contradiction lowered it. That
model conflates two things the mission (EPISTEMOS-05) insists must stay separate:

> **CONTRIBUTION ≠ TRUTH.**

When multiple agents (or people) contribute, the system must be able to answer: *what has been
**claimed**, by **whom**, on what **evidence**, what **contradicts** it, who **reviewed** it, what do
we actually **believe** and **why**, what **changed** that belief, and what **remains disputed** —
without a submission becoming truth merely because it was submitted, and without a majority vote
standing in for verification.

The design question: **extend the knowledge graph** (add reviewer/verdict fields to `Fact`,
overload confidence), or **introduce a separate claim graph**?

## Decision

Introduce a **claim graph** as new object kinds that **reuse** the existing machinery rather than
duplicating or overloading `Fact`.

- **`Claim`** (`claims.Claim`, `kind="claim"`) — a proposition someone asserted. It **exists**
  whether or not the system believes it. It is bitemporal like a `Fact` (valid + transaction time)
  and carries a lifecycle `status` (`open`/`retracted`/`superseded`) that is **distinct from belief**.
- **`Evidence`** (`kind="evidence"`) — a typed artifact (`document`/`uri`/`hash`/`dataset`/…). The
  full content need not be stored: a **URI + content hash** is a valid, integrity-checkable
  reference (§5). Evidence attaches to a claim with a **typed relation**
  (`supports`/`contradicts`/`weakens`/`derived_from`) — *attached is not supports* (§6).
- **`Review`** (`kind="review"`) — one reviewer's individual, preserved assessment
  (`confirm`/`dispute`/`reject`/`request_evidence`/`abstain`). Reviews are events, never collapsed
  into a score; multiple reviewers may disagree and **all** verdicts survive.

All three subclass the existing **`Envelope`**, so they inherit — for free and unforked — owner,
tenant/namespace, `source`, `confidence`, `derived_from`, the **hash-chained ledger**, the
**bitemporal** helpers, the **Knowledge-Spaces firewall** (`spaces`), and `explain`. Each is emitted
through the ledger (`CLAIM_ASSERTED`, `EVIDENCE_RECORDED`, `EVIDENCE_ATTACHED`, `CLAIM_REVIEWED`,
`CLAIM_ACCEPTED`/`REJECTED`, `CLAIM_RETRACTED`/`SUPERSEDED`) and projected — never written to the
store directly, so `rebuild_projection == replay` continues to hold for the whole collaborative state.

**Identities stay separate** (§3). `owner` = the *ingesting agent*; `claimant` = *who asserts it*
(may be a human, service, or other identity); `source` = the *external origin*; the reviewer is the
`owner` of a `Review`. None are collapsed — the same agent ingesting a human analyst's claim records
three distinct identities.

## Consequences

- The knowledge graph (`Fact`) is untouched: accepted knowledge remains a `Fact`, and the claim
  graph is the *provenance of how a contested statement becomes (or fails to become) one*. A Claim is
  not a Fact and does not appear in `current()`/belief-of-facts queries.
- Claims/evidence/reviews are searchable (`object_text` handles the new kinds) and space-scoped by
  the **same** firewall, so the four P0 leak invariants extend to them at no extra cost
  (`CLAIM_SPACE_LEAK = EVIDENCE_SPACE_LEAK = REVIEW_SPACE_LEAK = 0`).
- Belief is **derived**, not stored (ADR-029). Acceptance is **governed**, not a vote (ADR-029).

## Rejected alternatives

- **Overload `Fact` with reviewer/verdict fields** — rejected: it re-conflates contribution and
  truth (the exact bug), and a disputed contribution would pollute the believed knowledge graph.
- **Collapse reviews into a numeric trust score on the claim** — rejected: a score erases *who*
  disagreed and *why*; "majority is not truth" (§9) requires preserving individual verdicts.
- **A single universal `trust_score` across claimant/source/reviewer** — rejected: the trust
  dimensions are different questions and must stay separate; cross-dimension reputation is explicitly
  EPISTEMOS-07, out of scope here.
- **Deduplicate corroborating claims into one** — rejected: two agents asserting the same thing are
  **two** contributions (corroboration), not one; collapsing them destroys provenance (§ corroboration
  ≠ dedup).
