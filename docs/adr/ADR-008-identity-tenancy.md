# ADR-008 — Identity & tenancy: fail-closed, namespace-as-boundary

**Status:** Accepted (v0.1)

## Context
Multi-tenant isolation must be designed in, never added later (mission §14). The census shows
universally weak isolation (a `group_id` filter or opt-in access control).

## Decision
Every operation takes an explicit, immutable `Principal` (tenant, agent, namespace, optional human
principal, capabilities). There is **no ambient identity**; a missing/invalid principal raises
`IdentityError`. The **isolation boundary is `(tenant, namespace)`**: reads across it raise
`NotFoundError` (no existence leak), writes raise `TenantIsolationError`. Within a shared namespace
agents collaborate (shared reads) but **cannot clobber another agent's objects** (owner guard);
**agent-private memory is a per-agent namespace**. Capabilities gate operations (`assert`,
`supersede`, `retract`, `decide`, …). Store query methods also filter by scope (defense in depth).
EPISTEMOS is **not** a policy authority — a future NOMOS adapter attenuates capabilities; EPISTEMOS
never *grants* them (ADR-013).

## Consequences
- Cross-tenant/agent/namespace attacks fail closed (tested, and mutation-verified).
- Private vs shared memory is expressed compositionally via namespaces, no extra "private" flag.

## Rejected alternatives
- **`group_id`/scope-field filtering** (Graphiti/Mem0): one missing filter leaks; rejected.
- **Opt-in access control** (Cognee): not fail-closed; rejected.
- **A separate `private` boolean on objects**: redundant with namespaces; rejected.
