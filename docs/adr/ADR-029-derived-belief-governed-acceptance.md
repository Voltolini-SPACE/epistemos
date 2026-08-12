# ADR-029 — Belief is derived; acceptance is governed through a policy port

**Status:** Accepted (v0.5)

## Context

Given the claim graph (ADR-028), the system must answer *"what do we believe, and why?"* Two traps to
avoid: (1) storing belief as a boolean that some code path can flip (truth-by-write), and (2)
accepting a claim by counting votes (truth-by-majority). The mission forbids both and additionally
requires that **acceptance be a governed act** that a deployment can delegate to an external policy
decision point (e.g. NOMOS) **without the core depending on it** — EPISTEMOS must run standalone,
zero-egress, no LLM.

## Decision

**Belief is a pure function of the ledger-projected material** — never a stored field.
`claims.belief.derive_belief(claim, reviews, accepted, rejected)` returns an explainable record
`{state, why, reviews, governance}` with this precedence:

1. **lifecycle** — a `retracted`/`superseded` claim is `RETRACTED`/`SUPERSEDED` (short-circuit);
2. **governance** — a governed `rejected` ⟶ `REJECTED`; a governed `accepted` ⟶ `ACCEPTED`;
3. **review picture** — any live `dispute`/`reject` ⟶ `DISPUTED`; else confirmations ⟶ `SUPPORTED`;
   else ⟶ `PROPOSED`.

Two rules make this honest:

- **Majority is not truth (§9).** One live dispute yields `DISPUTED` even against many confirmations.
  Belief is not a tally.
- **Governance dominates but does not erase (§10).** A governed acceptance sets `ACCEPTED`, yet the
  `why` still **records any coexisting dispute** ("NOTE: 1 dispute/reject still on record"). The audit
  trail is whole; an override is visible as an override.

Belief is always computed over **only the reviews the caller may read** — `belief()` derives from
`_readable_reviews`, so a viewer who cannot see a restricted review does not have it folded into their
answer (and cannot infer it exists).

**Acceptance is governed through a policy port.** `accept_claim`/`reject_claim` require the
**`knowledge.accept`** capability (a *non-default* right — it is **not** in `_DEFAULT_CAPS`; ordinary
contribution and review are), then delegate the *decision* to a pluggable
`Policy = Callable[[PolicyRequest], PolicyDecision]`. The zero-config default is `LocalDefaultPolicy`:
deterministic, no network, no LLM — it demands the capability, refuses retracted/superseded claims,
and records the review picture in its reason **without** imposing a vote threshold. A deployment wanting
"N independent confirmations" or an external PDP plugs its own policy into `Engine(store, policy=…)`.

Two abuse guards are enforced **in the engine**, independent of whichever policy is installed:

- **The capability gate is load-bearing in the engine itself** — `require("knowledge.accept")` runs
  *before* the policy is consulted, so a permissive policy cannot let a capability-less principal
  accept. (This is proven by a dedicated adversarial test under an allow-all policy, and by mutation
  `claim_accept_cap_removed`.)
- **A claimant cannot govern their own claim** (`accept`/`reject`) into truth (§32) — self-*review*
  is allowed but **disclosed**; self-*acceptance* is denied.

## Consequences

- No code path can "set believed = true": belief only ever *derives*. Rebuilding the projection from
  the ledger reproduces every belief exactly (chaos-tested), including an accepted-with-coexisting-
  dispute claim.
- The core is standalone and sovereign; NOMOS (or any PDP) is an **optional** governance plug, wired
  by injection, never a build dependency. The MCP/network boundary stays outside the core.
- `explain_claim` surfaces the full picture — claimant/source, typed evidence, individual reviews
  (with `self_review` disclosed), derived belief + `why`, contradictions, space, temporal — with
  **authorization applied before traversal** (the v0.4 `explain` leak stays permanently closed).

## Rejected alternatives

- **Store a `believed: bool` / `accepted: bool` on the claim** — rejected: it is exactly the
  truth-by-write trap; any write path could forge it and the audit trail would not explain it.
- **Accept when confirmations ≥ threshold** — rejected as a *core* rule: that is truth-by-majority.
  Thresholds are a *policy* choice a deployment may install, not a law of the engine.
- **Let the policy be the only capability check** — rejected: it would make the truth gate
  defeatable by swapping in a lenient policy; the engine must enforce `knowledge.accept` itself.
