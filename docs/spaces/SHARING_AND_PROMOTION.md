# Sharing & Promotion (EPISTEMOS-04, SHIPPED)

Explicit only — there is no implicit sharing (mission §9). Promotion is not a move: the object's
prior placements and full lineage are preserved (§10).

## Explicit share (lateral)

`engine.share(principal, obj_id, into=space_id)` appends `space_id` to the object's `spaces` via a
`KNOWLEDGE_SHARED` event. Requires: the caller **owns** the object, and can **reach** the destination
(owns it, is a granted member, or it is tenant-wide). The origin placement is preserved.

## Promotion (monotone, up the lattice)

`engine.promote(principal, obj_id, into=space_id)` appends a placement whose visibility is **>= every
current placement** (a downward move is refused — `ValidationError`), via `KNOWLEDGE_PROMOTED`.
Promotion to `ORGANIZATION` or wider additionally requires the explicit `knowledge.promote`
capability — the **only** path toward PUBLIC.

```
PRIVATE ──share──▶ TEAM ──promote──▶ ORGANIZATION ──promote──▶ COMMUNITY ──promote──▶ PUBLIC
   │  each arrow = one appended ledger event; the object is never moved or rewritten
   ▼
 lineage preserved: the whole visibility history is reconstructable from the ledger
```

## Preserved provenance of the exposure

Each share/promote event records (mission §10/§15):

```
object_id · destination_space · source_spaces · shared_by | promoted_by · reason
transaction_time (ledger ts) · actor (who performed it)
```

Combined with the object's own `owner` (created_by) and `derived_from`/`supersedes` edges,
`explain()` can walk *who created it, who shared/promoted it, where it originated, why it changed* —
subject to the read firewall (a private ancestor is elided, never exposed).

## Contribution ≠ knowledge (mission §16)

Sharing/promoting a claim does not make it accepted truth. The v0.3 claim/belief separation is
unchanged: `Observation` (raw claim) vs `Fact` (believed), contradiction is first-class (rivals
coexist), `confirm` is corroboration-only (`delta >= 0`), and the four dimensions — source trust /
contributor identity / claim confidence / evidence strength — stay **separate** (§17), never a single
`trust_score`. A full claim-review pipeline and generational confidence are EPISTEMOS-05.

## What this does NOT do (deferred, mission §35)

No public community server, internet federation, subscriptions, global reputation, social ranking,
likes/upvotes, marketplace, central identity, mandatory cloud, or automatic sync. Local-first and
zero-egress are preserved: creating spaces introduces no telemetry/sync/discovery/upload
(`test_zero_egress` covers the full lifecycle including spaces).
