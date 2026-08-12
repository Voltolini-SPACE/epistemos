# Review model

A **Review** is one reviewer's individual, preserved assessment of a claim. Reviews are **events, not
a score** — multiple reviewers may disagree, and every verdict survives. Majority is not truth (§9).

## Shape

`claims.Review` (`kind="review"`) subclasses `Envelope`; the reviewer is the review's `owner`.

| field | meaning |
|-------|---------|
| `claim_id` | the claim being assessed |
| `verdict` | `confirm` / `dispute` / `reject` / `request_evidence` / `abstain` |
| `rationale` | free-text reasoning (optional) |
| `evidence_refs` | evidence the reviewer cites (each must be readable by the reviewer) |

## Capabilities

`review_claim(claim_id, verdict, …)` maps the verdict to the required capability:
`confirm → claim.confirm`, `dispute → claim.dispute`, otherwise `claim.review` (all default rights).
Reviewing requires **read access to the claim** — you cannot review what you cannot see (a
cross-space attempt raises `NotFoundError`, not an oracle).

## Visibility — a review inherits the claim's audience

A review is placed in the **same spaces as the claim it reviews**. So review visibility tracks claim
visibility exactly: everyone who can see the claim can see its reviews; no one else can
(`REVIEW_SPACE_LEAK = 0`). Belief is derived over **only the reviews the caller may read**.

## Self-review is allowed but disclosed

The claimant *may* review their own claim (it is a legitimate assessment), but `explain_claim` flags
it with `self_review: true`. What is **denied** is self-*acceptance* — a claimant cannot govern their
own claim into accepted truth (see `BELIEF_MODEL.md`, §32). Individual reviews are never merged,
deduplicated, or out-voted away; `explain_claim` returns each verdict with its reviewer and rationale.

See `ADR-028`, `ADR-029`.
