# ADR-024 — Knowledge Spaces: a visibility lattice orthogonal to the tenant boundary

**Status:** Accepted (v0.4)

## Context

v0.3 had one scoping construct, `(tenant, namespace)`. The EPISTEMOS-03 audit (finding B-02)
established that **namespace is a partition within the tenant, not an authorization boundary**: any
principal holding a token for a tenant could name any namespace in it, so "agent-private memory via
namespace" was only tenant-deep. To let a user share *selected* knowledge with another user/group
without exposing the rest of their private knowledge, EPISTEMOS-04 needs a real visibility boundary.

## Decision

Add **Knowledge Spaces**: a first-class visibility dimension **orthogonal** to tenant.

- **`Visibility`** is a total order: `PRIVATE(0) < TEAM(1) < ORGANIZATION(2) < COMMUNITY(3) <
  PUBLIC(4)` (`spaces.Visibility`, an `IntEnum`). The *ordinal* drives "can this audience see that
  level"; a space *name* drives membership. `kind` and `visibility` are kept as **separate fields**
  (a tenant may hold several spaces at one level).
- **A `KnowledgeSpace`** (`spaces.KnowledgeSpace`) is a store object (`kind="space"`), created by a
  `SPACE_CREATED` ledger event, scoped to one tenant. Never visible cross-tenant.
- **Objects carry `spaces: tuple[str, ...]`** (a new `Envelope` field). **Empty = PRIVATE to the
  owner** — the fail-closed default. No space object is needed for the private case, so the
  local-first single-agent flow requires zero configuration and reproduces v0.3 exactly.
- **Placement is append-only.** `share` (lateral) and `promote` (monotone up the lattice) append a
  space to an object's `spaces` via `KNOWLEDGE_SHARED`/`KNOWLEDGE_PROMOTED` events. The object's
  whole visibility history is reconstructable from the ledger; nothing is moved or rewritten (the
  A-12 append-only guarantee carries the lineage `source_spaces`/`shared_by`/`promoted_by`).
- **Fail closed everywhere.** `resolve_visibility(None) == PRIVATE`; an unknown/malformed value
  **raises** (never defaults *upward*). A dangling placement (space id with no space object) grants
  nobody access. A cross-tenant object is never readable.

Tenant stays the hard isolation boundary; namespace stays a within-tenant partition (retained,
unchanged). Space is the *third, orthogonal* field — the assessment listed "making namespace
silently mean space" as a REJECTED_DIRECTION, so namespace is neither renamed nor absorbed.

## Consequences

- **The B-02 correction ships:** within a namespace, an object is private to its owner by default;
  cross-agent access requires an explicit `share` into a space the reader is granted. The v0.3
  tests that relied on implicit shared-namespace reads were rewritten to the spaces model.
- **Backward compatible for the common case:** a v0.3 database (objects with no `spaces` field)
  projects to fully-PRIVATE; single-agent behaviour is byte-identical; `rebuild_projection == replay`
  holds. Legacy → PRIVATE, never PUBLIC (mission §34).
- **The visibility of an object is the union of its placements' levels**, so an object reaches
  PUBLIC only through an explicit, authorized, logged promotion — the P0 guard (ADR-026,
  `PRIVATE_PUBLIC_INVARIANT.md`).

## Rejected alternatives

- **Reuse namespace as the space** — rejected (B-02: namespace is not an authz boundary; would
  strand the partition semantics).
- **Store `visibility` on each object instead of a `space` reference** — rejected: visibility would
  drift from the space; a placement reference keeps one source of truth and supports multi-space
  placement (share then promote).
- **A single `visibility` enum with no space container** — rejected: `TEAM` needs *which* team
  (membership), which an ordinal alone cannot express.
