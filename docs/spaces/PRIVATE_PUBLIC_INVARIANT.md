# The PRIVATE→PUBLIC Invariant (EPISTEMOS-04 P0)

```
PRIVATE_TO_PUBLIC_IMPLICIT_FLOW = IMPOSSIBLE
PRIVATE_TO_PUBLIC_LEAK = 0
```

**Statement.** No object reaches an audience wider than its owner except through an explicit,
authorized, logged, monotone promotion event performed by a principal holding `knowledge.promote`.
Absence of configuration is PRIVATE; PUBLIC is never inferred.

## The single gate

Widening happens in exactly one place — `Engine._place` (share/promote). Placing into `ORGANIZATION`
or wider requires `knowledge.promote`, which is **not** in `_DEFAULT_CAPS`. There is no other code
path that adds a placement to an object. Every read surface then honours the placement through the
firewall ([AUTHORIZATION_PIPELINE](AUTHORIZATION_PIPELINE.md)).

## The adversarial battery (mission §11, §27) — all fail

`tests/spaces/test_private_public_invariant.py` runs each attack and asserts a private object is
observable through **no** surface (get, search on index + scan fallback, current/as_of, timeline,
facts_for, recall, explain, graph, export):

| Attack | Result |
|--------|--------|
| missing visibility | defaults PRIVATE (fail closed) |
| crafted import (rewrite scope) | refused — `IntegrityError` (A-01 holds under spaces) |
| crafted import (fabricated space placement) | dangling → grants nobody (empty-target import) |
| cross-space id reference (private ancestor of a shared object) | `explain` elides the ancestor |
| search score / rank / count | unauthorized candidates removed before scoring → no leak |
| degraded-index fallback | scan enforces the same firewall |
| stale capability after revoke | denied immediately, everywhere |
| forged membership via `Principal` | grants nothing (membership is server-side) |
| promotion toward PUBLIC without capability | `AuthorizationError`; object stays private |
| graph traversal (private node behind a public one) | edge/node not revealed |
| tenant / namespace / principal confusion | fail closed (`test_authz_unit.py`) |
| promotion replay / double promotion | append-only; idempotent placement; rebuild-stable |

## Recovery (mission §29)

After crash + rebuild: `NO_PRIVATE_LEAK`, `LEDGER_VALID`, `PROJECTION_REBUILDABLE`,
`INDEX_REBUILDABLE`, `AUTHORIZATION_INTACT` (`test_space_chaos.py`). Grants and placements are
projected from the ledger, so authorization is reconstructed from authoritative state alone.

## Residual (documented, not a leak)

The FTS MATCH resolves over the whole namespace before the space predicate is applied, so search
*latency* couples across spaces within a namespace (the OV-04 timing coupling). This leaks no
content/score/count; per-space index partitioning (a follow-up) removes the timing side-channel.
`CROSS_SPACE_RETRIEVAL_LEAK = 0` for content; timing isolation is the deferred hardening.
