# ADR-025 — Capability-based authorization; roles are capability sets

**Status:** Accepted (v0.4)

## Context

Sharing needs authorization. The mission is explicit (§6-7): enforcement is by **capability**, never
by role name — there must be no `if role == "owner": allow_everything()`. And membership must be
authoritative, not client-claimed (the A-01/A-11 lesson).

## Decision

- **Capabilities are the unit of authority.** `Principal.capabilities` is an opaque frozenset. The
  EPISTEMOS-04 vocabulary (`identity.KNOWLEDGE_CAPABILITIES`): `knowledge.{read,search,contribute,
  share,review,promote,retract}`, `claim.{confirm,dispute}`, `evidence.attach`,
  `provenance.read`/`history.read`/`graph.traverse`, `space.{create,read,manage,invite}`.
- **Roles are convenience sets**, expanded to capabilities before evaluation. VISITOR/MEMBER/
  CONTRIBUTOR/REVIEWER/CURATOR/OWNER are *documented* capability bundles; the engine never checks a
  role name (proven by `test_role_is_only_a_capability_set_not_authority`).
- **The dangerous capabilities are NOT in `_DEFAULT_CAPS`.** A default principal can read, assert,
  and `space.create`/`space.read` — but has **no** `knowledge.share`/`knowledge.promote`. So no
  default principal can move knowledge toward PUBLIC (fail closed, the P0).
- **Placement authority is gated by DESTINATION visibility, not by the operation.** `share`/`promote`
  require the caller to own the object *and* be able to reach the destination space (own it, be a
  granted member, or it is tenant-wide). Placing into `ORGANIZATION` or wider additionally requires
  the explicit `knowledge.promote` capability — the single gate on the path to PUBLIC.
- **Membership is server-side.** `grant_capability`/`revoke_capability` emit
  `CAPABILITY_GRANTED`/`CAPABILITY_REVOKED` ledger events projected into `grant` objects
  (`active: bool`). The read decision reads *projected* grant state via `is_member`, never a
  caller-supplied `Principal` field — a client that forges capabilities/memberships on its Principal
  gains nothing (`test_client_cannot_forge_membership_via_principal`). Space *owners* (or `admin`,
  or holders of `space.manage`) administer their own space's membership.
- **Agents are principals too (§23).** No automatic exception because a principal is an agent — the
  same capability gating applies (`test_agent_principal_is_subject_to_capabilities`).
- **Temporal revocation (§22).** A revoke flips the grant `active=False`; the current decision denies
  immediately, while the historical fact that access existed remains in the ledger (auditable). No
  stale-capability replay: the decision never trusts a token/claim, only projected active grants.
  Grant/revoke survive `rebuild_projection` (deterministic replay).

EPISTEMOS **enforces** these mechanics; it does **not** author policy. A future NOMOS (or any PDP)
attenuates which principal *may* hold `knowledge.promote`; EPISTEMOS checks the capability is present
and records the event. NOMOS is not a mandatory dependency — the default-caps path fails closed.

## Consequences

- Sharing is safe by construction: a leak toward PUBLIC requires an authorized, logged promotion by
  a principal explicitly granted `knowledge.promote`.
- The capability names are not frozen as a public API (mission §33) — they are enforcement tokens;
  the SDK/REST surface is deferred until the model stabilizes.

## Rejected alternatives

- **Role-name checks** — rejected (mission §7; a name is not authority).
- **Membership on the Principal** — rejected: a client could claim it; membership is projected
  server state.
- **A single `trust_score`** collapsing source-trust / contributor-reputation / confidence — rejected
  (§17; kept as separate dimensions, unchanged from v0.3).
