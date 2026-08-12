# Capability Model (EPISTEMOS-04, SHIPPED)

Normative decision: [ADR-025](../adr/ADR-025-capability-authorization.md).

## Capabilities are the unit of authority

Authorization is by **capability**, never by role name (mission §7 — there is no
`if role == "owner": allow`). `Principal.capabilities` is an opaque frozenset. The vocabulary
(`identity.KNOWLEDGE_CAPABILITIES`):

```
knowledge.read  knowledge.search  knowledge.contribute  knowledge.share
knowledge.review  knowledge.promote  knowledge.retract
claim.confirm  claim.dispute  evidence.attach
provenance.read  history.read  graph.traverse
space.create  space.read  space.manage  space.invite
```

## Roles = capability sets

Convenience bundles expanded to capabilities before evaluation. The engine never checks a role name.

| Role | Capabilities (illustrative) |
|------|------------------------------|
| VISITOR | knowledge.read, space.read |
| MEMBER | + knowledge.search |
| CONTRIBUTOR | + knowledge.contribute, knowledge.share |
| REVIEWER | + knowledge.review, claim.confirm, claim.dispute |
| CURATOR | + knowledge.promote, space.manage, space.invite |
| OWNER | + knowledge.retract, space.create |

Proven: `test_role_is_only_a_capability_set_not_authority` (a principal *named* "owner" without the
capability is still denied).

## Fail-closed defaults

`_DEFAULT_CAPS` = read/assert/supersede/retract/contradict/confirm/decide/ingest/export +
`space.create`/`space.read`. It does **NOT** include `knowledge.share`/`knowledge.promote`, so **no
default principal can move knowledge toward PUBLIC**. Placing into `ORGANIZATION` or wider requires
the explicit `knowledge.promote` capability — the single gate on the path to PUBLIC.

## Membership is server-side

`grant_capability`/`revoke_capability` emit `CAPABILITY_GRANTED`/`CAPABILITY_REVOKED` ledger events,
projected into `grant` objects (`active: bool`). The read decision reads the **projected** grant
state (`Engine._is_member`), never a caller-supplied `Principal` field:

- forging capabilities/memberships on a client `Principal` grants nothing
  (`test_client_cannot_forge_membership_via_principal`);
- only a space **owner** (or `admin`/`space.manage`) administers its membership;
- **temporal revocation (§22):** revoke flips `active=False`; the current decision denies at once,
  the historical grant stays auditable in the ledger; grants/revokes survive `rebuild_projection`
  (`test_grant_revoke_are_ledger_events_and_rebuild`, `test_stale_capability_after_revoke_denies`);
- **agents are principals (§23):** no automatic exception
  (`test_agent_principal_is_subject_to_capabilities`).

## EPISTEMOS enforces, it does not grant

Whether a principal *may hold* `knowledge.promote` is a policy decision for NOMOS or another PDP
(not a mandatory dependency). EPISTEMOS checks the capability is present and records the event. The
capability names are enforcement tokens, **not a frozen public API** (mission §33).
