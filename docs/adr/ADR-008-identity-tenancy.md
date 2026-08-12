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

## EPISTEMOS-03 correction: namespace is a partition, not an authorization boundary

The v0.1 phrasing "namespace-as-boundary" and "agent-private memory is a per-agent namespace"
**oversold** what a namespace provides (audit finding B-02). The precise model is:

- **`tenant` is the hard isolation boundary.** No operation crosses it.
- **`namespace` is a *partition within* the tenant**, not a per-agent access-control boundary. Any
  principal that already holds a token for a tenant can construct `Principal(tenant, agent,
  namespace=X)` for *any* `X` in that tenant (and the REST `X-Eps-Namespace` header exposes the same
  choice). Cross-namespace *reads* return `None`/`NotFoundError` only when you query with a
  **different** namespace — they are not protected *against* an agent that chooses to name your
  namespace.

So "agent-private memory via namespace" holds only to the depth of the tenant boundary: it partitions
cooperating agents, it does not defend one agent's namespace from another agent in the same tenant.
True per-agent / per-space authorization (a visibility lattice with fail-closed placement and
capability-gated access) is deferred to **EPISTEMOS-04 (Knowledge Spaces + capability model)** — see
`docs/collaboration/KNOWLEDGE_SPACES.md`. This ADR is not reverted (the tenant boundary and owner
guard are real and mutation-verified); it is corrected to state the namespace's actual guarantee.

## Rejected alternatives
- **`group_id`/scope-field filtering** (Graphiti/Mem0): one missing filter leaks; rejected.
- **Opt-in access control** (Cognee): not fail-closed; rejected.
- **A separate `private` boolean on objects**: redundant with namespaces; rejected. *(Note:
  EPISTEMOS-04 revisits this: an explicit `visibility` field IS warranted once spaces exist, because
  visibility is orthogonal to the tenant/namespace partition — see the collaboration assessment.)*
