# Claim model

A **Claim** is a proposition someone asserted. It **exists independently of whether the system
believes it** — the core distinction of EPISTEMOS-05: *contribution ≠ truth*.

## Shape

`claims.Claim` (`kind="claim"`) subclasses `Envelope`, so it carries the usual owner / tenant /
namespace / `source` / `confidence` / `derived_from` / `spaces` / bitemporal machinery, plus:

| field | meaning |
|-------|---------|
| `subject`, `predicate`, `object` | the proposition (object optional) |
| `claimant` | **who asserts it** — may be a human/service/other identity, distinct from `owner` |
| `contributor_kind` | `human` / `agent` / `service` / `organization` |
| `valid_from`, `valid_to` | world (valid) time — when the proposition is *about* |
| `tx_from`, `tx_to` | transaction time — when it was asserted / closed in the system |
| `status` | lifecycle: `open` → `retracted` / `superseded` (distinct from **belief**) |

## Three separate identities (§3)

`owner` = the **ingesting agent** (who wrote it into the store) · `claimant` = **who asserts it** ·
`source` = the **external origin**. The reviewer is the `owner` of a `Review`. None are collapsed:
one agent ingesting an analyst's claim sourced from a filing records three different identities.

## Lifecycle vs belief

`status` is what the *claim* is (open/retracted/superseded). **Belief** is a separate, *derived*
question (see `BELIEF_MODEL.md`). A claim can be `open` and `disputed`, or `open` and `accepted`.
Retraction and supersession are **append-only, first-close-wins**: the claim is never deleted, and a
second retract of an already-closed claim raises `ConflictError`.

## Operations

- `create_claim(...)` — requires `claim.create` (a default right). PRIVATE by default; a `space`
  argument places it. Placing directly into ORG+ requires `knowledge.promote`.
- `retract_claim(...)` — requires `claim.retract`; owner-guarded; belief becomes `RETRACTED`.
- Corroboration ≠ dedup: two agents asserting the same proposition are **two** claims, each with its
  own `claimant`.

Every mutation is a ledger event (`CLAIM_ASSERTED` / `CLAIM_RETRACTED` / `CLAIM_SUPERSEDED`) and is
reconstructable by replay. See `ADR-028`.
