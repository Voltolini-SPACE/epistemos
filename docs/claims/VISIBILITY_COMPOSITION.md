# Visibility composition (§15)

The claim graph is layered on the **Knowledge-Spaces firewall** (ADR-024/025/026). Claims, evidence
and reviews are ordinary space-scoped objects, so the four P0 leak invariants hold for them:

```
CLAIM_SPACE_LEAK       = 0     a claim outside your spaces is invisible
EVIDENCE_SPACE_LEAK    = 0     evidence outside your spaces is invisible
REVIEW_SPACE_LEAK      = 0     a review outside your spaces is invisible
PRIVATE_TO_PUBLIC_LEAK = 0     private evidence never leaks through a public claim
```

The subtle one is **composition**: a claim and the objects *behind* it can have **different**
visibilities. A widely-shared claim may cite private evidence, or carry a restricted review. Making
the claim visible must **not** transitively expose those.

## The rule

Every derived/aggregated read re-authorizes each referenced object **individually**, against the
caller — visibility never inherits transitively from the claim to its evidence/reviews/source.

- **`claim_evidence(claim)`** returns only the evidence links whose evidence object the caller
  `_can_read`. A public claim + private evidence ⟶ the evidence owner sees the link, everyone else
  sees an empty list. (Guarded by mutation `claim_evidence_readability_removed` and
  `test_public_claim_does_not_expose_private_evidence`.)
- **`belief` / reviews** derive over `_readable_reviews` only. A restricted review is neither folded
  into another viewer's belief nor listed for them.
- **`explain_claim`** applies authorization **before traversal**: unreadable evidence, reviews,
  source and genealogy are **elided, never exposed** (the v0.4 `explain` ancestor-leak stays closed).
- **`source`** is shown only if the source object is readable in scope (the B-06 rule, applied to
  claims via `_scoped_source_view`).
- **Attach requires read of both sides** — you cannot attach evidence you cannot see, so links are
  never created across a boundary you lack.

## Consequence

Two members of the same space get identical, complete pictures. A caller who can see a claim but not
some object behind it gets a *truthful but redacted* view — the claim, minus exactly the parts they
are not entitled to — with no count, timing, or existence oracle betraying what was withheld.
