# Knowledge Space Model (EPISTEMOS-04, SHIPPED)

Normative decision: [ADR-024](../adr/ADR-024-knowledge-spaces.md). This document describes what
v0.4 actually ships.

## Two orthogonal axes

| Axis | Question | Type | Enforcement |
|------|----------|------|-------------|
| **Tenant** | whose data is this? | hard isolation | never crossed (`TenantIsolationError`) |
| **Namespace** | which partition within the tenant? | partition (retained from v0.3) | not an authz boundary (B-02) |
| **Space** | who may see it (visibility)? | ordered lattice | the read firewall (ADR-026) |

Tenant and space are **different entities** (mission §3): tenant is ownership/isolation, space is
visibility. A `TEAM`-visible object still belongs to exactly one tenant and is never visible to
another tenant.

## Visibility lattice

`spaces.Visibility` — a total order:

```
PRIVATE(0) < TEAM(1) < ORGANIZATION(2) < COMMUNITY(3) < PUBLIC(4)
```

The **ordinal** decides "can this audience see that level"; a space **name** decides membership.
`kind` (the space type) and `visibility` (the lattice level) are **separate fields** — the initial
kinds map 1:1 to levels, but the schema keeps them distinct so a tenant can hold several spaces at
one level without reinterpreting it.

## The `KnowledgeSpace` object

`spaces.KnowledgeSpace`, stored as a `kind="space"` object created by a `SPACE_CREATED` event:

```
id · tenant · name · kind · visibility · owner · created_at · policy · metadata
```

Scoped to one tenant; `get_space` never returns a cross-tenant space. Control-plane objects
(`space`, `grant`) never appear in knowledge queries (search/recall exclude them).

## Object placement

Every object carries `spaces: tuple[str, ...]` (a new `Envelope` field):

- **`spaces == ()` → PRIVATE to the owner** — the fail-closed default. No space object needed; the
  local-first single-agent case needs zero configuration and reproduces v0.3 exactly.
- `spaces == (s1, …)` → readable if the principal can access **any** placed space.

An object reaches a wider audience **only** by an explicit `share` (lateral) or `promote` (up the
lattice) that appends a placement — an append-only ledger event carrying the lineage. The object's
whole visibility history is reconstructable from the ledger; placement never rewrites the object.

## Fail-closed everywhere (mission §5)

`resolve_visibility(None) == PRIVATE`; unknown/invalid **raises** (never defaults upward). A dangling
placement (space id with no space object) grants nobody access. Missing principal, unknown space,
cross-tenant object → deny. Tests: `test_spaces_model.py`, `test_authz_unit.py`.

## Backward compatibility

A v0.3 database (objects without `spaces`) projects to fully-PRIVATE; single-agent behaviour is
byte-identical; `rebuild_projection == replay` holds. Legacy → PRIVATE, never PUBLIC (§34). Tests:
`test_backward_compat.py`.
