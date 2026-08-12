# EPISTEMOS — Knowledge Spaces (visibility lattice, orthogonal to tenant)

> **Status: DESIGN — DEFERRED to EPISTEMOS-04.** Nothing in this document ships in v0.3.
> Per the EPISTEMOS-03 owner addendum (§28) and the collaborative assessment
> (`COLLABORATIVE_KNOWLEDGE_MODEL.md`), v0.3 ships **only** current-defect fixes and
> backward-compatible hardening. Every mechanism below is classified
> **`FOUNDATIONAL_PRIMITIVE` / EPISTEMOS-04**, is **additive**, and is **backward-compatible**:
> a standalone, offline, single-agent EPISTEMOS with no space configured keeps behaving exactly
> as it does at tag `epistemos-v0.2.0` (`0451301`).
>
> This file is the detailed design behind the anchor's line
> `KNOWLEDGE_SPACES_MODEL = DESIGNED (space + visibility lattice, orthogonal to tenant;
> fail-closed PRIVATE default) — EPISTEMOS-04`. It is written to be consistent with that
> assessment's decisions (Q1, Q2, Q6), its classification table, and its mandated output block.
> Where the two disagree, the anchor governs and this file is wrong.

---

## 1. Why this exists (the gap the audit found)

EPISTEMOS v0.2 has exactly **one** scoping construct: `(tenant, namespace)`. Both are carried
on `Principal` and stamped onto every object's `Envelope`:

- `src/epistemos/identity/__init__.py` — `Principal.scope` returns `(self.tenant, self.namespace)`;
  `guard_scope` refuses any `tenant != self.tenant` (hard `TenantIsolationError`) and any
  `namespace != self.namespace`.
- `src/epistemos/model/__init__.py` — `Envelope` carries `tenant` and `namespace` and **no**
  visibility field. There is nothing today that expresses "who, beyond this exact
  `(tenant, namespace)`, may see this object."

Audit finding **B-02** (EPISTEMOS-03) proved the consequence: the REST header `X-Eps-Namespace`
lets any token in a tenant read/write any namespace in that tenant, so the informal story
"agent-private memory via namespace" was only ever **tenant-deep**. The audit reclassified it:

> *namespace is a **partition within** the tenant isolation boundary, not a per-agent
> authorization boundary.* (B-02, `OVERCLAIM → FOUNDATIONAL`; ADR-008 corrected.)

The anchor answers this in **Q1** and **Q2**:

- **Q1** — the current model gives a two-level scope (`tenant` = hard isolation, `namespace` =
  unordered partition). A visibility lattice PRIVATE < TEAM < ORG < COMMUNITY < PUBLIC is an
  **ordering** that namespaces do not have (namespaces are unordered peers with no
  cross-visibility). So spaces are **a new dimension, not a rename of namespace**.
- **Q2** — **tenant and space must be different entities.** Tenant answers *whose data this is*
  (ownership / isolation). Space answers *who may see it* (visibility, along a lattice).
  Collapsing them is precisely what produced B-02.

Knowledge Spaces closes that gap by adding `space` + `visibility` as first-class, fail-closed
fields **orthogonal** to tenant.

---

## 2. The two axes are orthogonal

| Axis | Question | v0.2 construct | EPISTEMOS-04 construct | Nature |
|------|----------|----------------|------------------------|--------|
| **Tenant** | *Whose data is this? Who owns/isolates it?* | `Principal.tenant` → hard `TenantIsolationError` | unchanged | Hard isolation. Never crossed implicitly. |
| **Namespace** | *Which partition inside the tenant?* | `Principal.namespace` | unchanged (kept for back-compat) | Partition, **not** an authz boundary (B-02). |
| **Space** | *Along the visibility lattice, who may see this?* | *(does not exist)* | `Envelope.space` + `Envelope.visibility` | Ordered visibility. Fail-closed PRIVATE. |

Orthogonality is the whole point: a `TEAM`-visible object still belongs to exactly one tenant and
is never visible to another tenant. **Sharing is not a hole in tenant isolation** — it is a
separate, additive predicate applied *within* whatever isolation the tenant already guarantees.
Cross-tenant sharing, when it eventually exists, is federation (EPISTEMOS-06: signed
instance-to-instance Knowledge Packages), never a widening of the in-process tenant guard.

```
   TENANT  (ownership / hard isolation — orthogonal, never implicitly crossed)
     │
     ├── acme ──────────────────────────────────────────────┐
     │      objects here carry a visibility on the lattice:  │
     │                                                        │
     │      PRIVATE  <  TEAM  <  ORGANIZATION  <  COMMUNITY  <  PUBLIC
     │      (narrowest)                                   (widest)
     │
     └── globex ── its own PRIVATE..PUBLIC lattice, disjoint from acme's
```

---

## 3. The visibility lattice

`visibility` is a **totally ordered** enum. "Higher" means "visible to a strictly larger
audience". Ordering is what lets retrieval reason about it (a namespace enum could not).

| Level | Ordinal | Audience (within the tenant) | Maps to v0.2 as |
|-------|--------:|------------------------------|-----------------|
| `PRIVATE` | 0 | The owning agent only. | today's effective single-agent behaviour |
| `TEAM` | 1 | An explicitly named team of agents. | *(new)* |
| `ORGANIZATION` | 2 | All agents in the tenant/org. | *(new — resembles today's tenant-wide namespace read)* |
| `COMMUNITY` | 3 | A named federation/community of consumers. | *(new; realized via EPISTEMOS-06 packages)* |
| `PUBLIC` | 4 | Anyone the deployment exposes. | *(new)* |

Design rules for the lattice:

1. **`PRIVATE` is the bottom and the default.** No object is born anywhere else (§4).
2. **Ordering is the only comparison.** Retrieval asks "is this object's visibility reachable by
   the caller's authorized-space set?" — it never string-matches a level name.
3. **The enum is closed and additive.** New levels, if ever needed, insert into the order; they
   never reinterpret an existing level (mirrors how `ledger.Op` is an open set of names that
   never redefines old ones).
4. **`space` names a concrete container; `visibility` is that container's lattice level.** A tenant
   may have many `TEAM` spaces (`team:payments`, `team:risk`); each is a distinct `space` at the
   same `visibility` ordinal. This is why both fields exist: the ordinal drives comparison, the
   name drives membership.

---

## 4. Fail-closed default: PRIVATE unless explicitly placed

**Every object is PRIVATE unless it was explicitly placed in a higher space. Absence of
configuration is PRIVATE, never PUBLIC.** This is the addendum's P0 ("private must never leak")
expressed as a construction invariant, and it matches how the codebase already fails closed:

- `identity.validate_name` / `require_principal` refuse ambient identity — an operation with no
  `Principal` is refused, never defaulted.
- `Envelope.__post_init__` validates on construction; "no field exists without a reason."
- `core._guard_payload_scope` takes scope from the **sealed record header**, never from
  attacker-supplied payload (the A-01 fix).

EPISTEMOS-04 extends the same posture to visibility:

```
def _resolve_visibility(explicit: str | None) -> Visibility:
    # No inference from environment, tenant config, or "looks public".
    # Missing / unknown / malformed  ->  PRIVATE  (fail closed).
    if explicit is None:
        return Visibility.PRIVATE
    try:
        return Visibility(explicit)      # closed enum; unknown value raises
    except ValueError:
        raise ValidationError("unknown visibility; refusing to guess")  # never default UP
```

Hard constraints this encodes (all non-negotiable per the assessment):

- **Never infer PUBLIC from absence of config.** A parse failure, a missing field, an unknown
  level, a migrated legacy object with no `visibility` → all resolve to `PRIVATE`.
- **Promotion is always explicit and always upward through an authorized action** (§6). There is
  no implicit or automatic promotion, and no batch job that raises visibility.
- **Placement is owner-gated.** Reusing today's `Principal.guard_owner`: an agent may place its
  own objects into a space it is authorized for; it cannot place another agent's object without
  `admin` (same rule that guards `supersede`/`merge_entities`).

---

## 5. Backward compatibility: `(tenant, namespace)` maps forward cleanly

The v0.2 world is reproduced by treating **PRIVATE space as today's behaviour**. Nothing an
existing caller does changes.

| v0.2 today | EPISTEMOS-04 forward mapping |
|------------|------------------------------|
| Object created with `(tenant, namespace)`, no visibility concept | `visibility = PRIVATE`, `space = <owning agent's private space>`. Identical retrieval result. |
| `Principal.scope == (tenant, namespace)` | Still valid. The scope predicate *extends* to `(tenant, authorized-space-set)`; for a caller with only its PRIVATE space, the authorized set is a singleton and the predicate collapses to today's exact-match. |
| `namespace` partition | **Unchanged and retained.** Namespace stays a within-tenant partition. Space is a *second, orthogonal* field; it does not replace, rename, or absorb namespace (the assessment lists "making `namespace` silently mean `space`" as a **REJECTED_DIRECTION**). |
| Legacy ledger / export with no `visibility` in payloads | On projection (`core._apply`), a missing `visibility` resolves to `PRIVATE` (§4). Replaying an old ledger yields a fully-PRIVATE graph — the safe interpretation. |
| `schema_version = 1` objects | A migration adds `space`/`visibility` defaulting to PRIVATE; because the default reproduces prior behaviour, the migration is **information-preserving and non-destructive**. |

Because the default is the identity transform, **`rebuild_projection()` over a pre-EPISTEMOS-04
ledger reconstructs the same observable state** — preserving the audit's load-bearing
"`rebuild_projection == replay`" invariant.

---

## 6. Promotion PRIVATE → TEAM → ORG → COMMUNITY → PUBLIC, preserving lineage

Promotion is a **monotone step up the lattice**, recorded as an **append-only ledger event** —
never an in-place edit of the object's visibility that would erase where it came from. This reuses
the mechanism the anchor validates in **Q3**: the ledger `Op` set is open, `_apply` already
projects new event types generically, and genealogy is preserved forever (the A-12 fix guarantees
the past cannot be rewritten).

Following addendum §3, promotion/sharing events carry these fields **as ledger payload**, so the
genealogy of *who exposed what to whom, when* is permanent and queryable via `explain()`:

| Field | Meaning |
|-------|---------|
| `created_by` | agent/principal that first created the object (already `Envelope.owner`) |
| `shared_by` | agent that placed it into a space (a lateral share, no level change) |
| `reviewed_by` | agent that reviewed the claim before promotion (links to EPISTEMOS-05 review) |
| `promoted_by` | agent that performed this upward step |
| `source_space` | the space it moved **from** |
| `destination_space` | the space it moved **to** (its `visibility` ordinal ≥ source) |

New ledger `Op` names (additive, exactly like the existing open set in `ledger/__init__.py`):

```
Op.KNOWLEDGE_SHARED     = "knowledge_shared"      # lateral placement into a space
Op.KNOWLEDGE_PROMOTED   = "knowledge_promoted"    # upward step on the lattice
Op.CLAIM_REVIEWED       = "claim_reviewed"        # (EPISTEMOS-05 review pipeline)
```

Rules:

- **Monotone by default.** `destination_space.visibility >= source_space.visibility`. A *downward*
  move (de-promotion / redaction) is a distinct, separately-authorized event, not a silent
  overwrite — and it does not delete history (the object was, verifiably, once more visible).
- **Promotion never rewrites the object.** As with `supersede`, the prior state remains in the
  ledger; promotion appends. `explain()` walks `created_by → shared_by → reviewed_by →
  promoted_by` the same way it already walks `derived_from`/`supersedes`/`contradicts`.
- **EPISTEMOS enforces the mechanics; it does not grant the right.** Whether a given
  `promoted_by` *may* promote to `PUBLIC` is a **policy decision** for NOMOS or another PDP
  (assessment Q12). EPISTEMOS checks the capability is present and records the event; it never
  decides the policy. NOMOS is **not** a mandatory dependency — the default-caps path
  (`_DEFAULT_CAPS`, which does **not** include a promote/publish cap) fails closed when no
  authority is wired.
- **The PRIVATE→PUBLIC leak invariant** (assessment Q9/Q11, its own EPISTEMOS-04 deliverable) is
  the guard that no object reaches a wider audience except through such an authorized, logged,
  monotone promotion event. This file assumes that invariant; `THREAT_MODEL.md` specifies it.

```
 PRIVATE ──promote──▶ TEAM ──promote──▶ ORG ──promote──▶ COMMUNITY ──promote──▶ PUBLIC
    │  each arrow = one appended ledger event carrying
    │  {created_by, shared_by, reviewed_by, promoted_by, source_space, destination_space}
    ▼
 lineage is never lost: the object's whole visibility history is reconstructable from the ledger.
```

---

## 7. Retrieval stays candidate-boundary-first

This is **P0** and the anchor's **Q6**: visibility must be applied *before* candidates are
exposed, so that existence, metadata, and timing of out-of-scope content cannot leak. v0.2 is
**already** candidate-boundary-first, which is exactly why this extends cleanly.

Today the scope predicate is enforced *inside the query*, not in a post-filter:

- `src/epistemos/index/fts.py::search` —
  `SELECT ... FROM fts_idx WHERE fts_idx MATCH ? AND tenant = ? AND namespace = ?`.
  The tenant/namespace filter is part of the SQL, not a Python filter applied after a global
  fetch. (The mutant `idx_search_tenant_leak` that drops this filter is killed.)
- `core.Engine.search` hands `principal.tenant, principal.namespace` down to the retriever; the
  scan path iterates `store.objects(tenant, namespace)` / `store.facts(tenant, namespace, ...)`.
  There is **no** global-retrieve-then-filter path.

EPISTEMOS-04 changes the predicate from `(tenant, namespace)` to
`(tenant, authorized-space-set)` — and keeps it inside the query:

```
-- v0.2 (today)
WHERE fts_idx MATCH ? AND tenant = ? AND namespace = ?

-- EPISTEMOS-04 (candidate-boundary-first, unchanged posture)
WHERE fts_idx MATCH ?
  AND tenant = ?                       -- hard isolation, unchanged
  AND space  IN (/* caller's authorized-space set */ ?, ?, ...)
```

The authorized-space set is resolved from the caller's `Principal` **before** the query runs
(its PRIVATE space always; plus any TEAM/ORG/… spaces its capabilities admit). Consequences:

- **No existence oracle across spaces.** An object the caller may not see is filtered *in the
  index/store*, so it never appears as a candidate, a count, or a latency signal — the same
  property that closed B-01's `get()` oracle and B-06/B-07's global-count oracle.
- **`CROSS_SPACE_RETRIEVAL_LEAK` reduces to keeping this predicate authoritative** (anchor Q6):
  the security property is "the space predicate is applied at the candidate boundary and is never
  bypassed," exactly analogous to today's tenant predicate.
- **Fail-closed on an empty authorized set.** If a caller resolves to *no* authorized spaces
  (misconfiguration, missing capability), the predicate matches its PRIVATE space only — never
  "all spaces."

---

## 8. Per-space index partitioning (perf note, OV-04)

Correctness and cost are separate concerns here, and the audit is precise about which is which.

- **Correctness today: safe.** The tenant/namespace (and future space) columns filter at the
  query boundary; the result set is always correctly scoped. There is **no leak** (OV-04 is
  explicitly *not* a leak).
- **Cost today: coupled.** Because `fts_idx` is a **single shared FTS5 table**, `MATCH` resolves
  across *all* rows before the `tenant`/`namespace` filter narrows them. A neighbour's corpus
  therefore inflates *your* search **latency** (OV-04 / B-07-index measured this). Under a space
  model, a large `PUBLIC`/`COMMUNITY` corpus would inflate every small `PRIVATE` search.

**EPISTEMOS-04 partitions the index per space** so cost is isolated as well as correctness —
either separate FTS5 tables per `(tenant, space)` or a partitioned/covering column that lets
`MATCH` prune before scoring. This is classified `CURRENT_HARDENING (perf)` / EPISTEMOS-04 in the
assessment table. It is a performance change only: it must not alter which rows are returned, and
the shared-predicate parity between the index path and the scan fallback (ADR-021,
`test_fallback_parity.py`) must continue to hold across the partition.

---

## 9. "Search across spaces" — labelled, explainable results (addendum §12)

When a caller is authorized for more than its PRIVATE space, a single search may legitimately span
several spaces. Each result must be **self-explaining about its origin and why the caller may see
it** — no bare id that hides where it came from. Extending the result shape already returned by
`core.Engine.search` (which today emits `retrieval_method`, `temporal_state`, `why_returned`):

```
{
  "id": "fact_…",
  "kind": "fact",
  "score": 0.82,
  "retrieval_method": "fts5-bm25+structural+temporal+authority",
  "temporal_state": "believed",
  "why_returned": "lexical match on 'settlement'; believed now",

  "origin_space":  "team:payments",          // the concrete space the object lives in
  "visibility":    "TEAM",                    // its lattice level
  "why_accessible":"caller holds capability 'read:team:payments'"  // NOT 'it was public'
}
```

Requirements for the added fields:

- **`origin_space`** and **`visibility`** name the object's actual container and level — surfacing,
  not hiding, cross-space provenance.
- **`why_accessible`** states the *authorization reason* the caller sees this result (which
  capability / membership admitted the object's space). It is never "absence of a restriction":
  fail-closed means access is always a positive grant, so the reason is always nameable.
- The label is **descriptive of enforcement already done at the candidate boundary** (§7), not a
  second filter. A result that could not be labelled with a real `why_accessible` should never
  have been a candidate in the first place.

This keeps the four dimensions the assessment insists on separate visible and un-collapsed in the
output: **source trust** (`Source.trust`), **claim confidence** (`Envelope.confidence` /
`score_components`), **evidence strength** (EPISTEMOS-05), and now **access/visibility**
(`visibility` + `why_accessible`) — none of which is the same as any other, and none of which
means "verified fact." AGENT_OUTPUT placed in a COMMUNITY space is still a *claim*, not truth.

---

## 10. What exists today vs. what is proposed

| Property | Exists today (v0.2, file evidence) | Proposed (EPISTEMOS-04) |
|----------|-----------------------------------|-------------------------|
| Hard tenant isolation | ✅ `identity.guard_scope`; killed cross-tenant mutants | unchanged |
| Namespace partition | ✅ `Principal.namespace`, `Envelope.namespace` | unchanged; **not** repurposed |
| Visibility lattice field | ❌ no `visibility`/`space` on `Envelope` | ➕ `space` + `visibility`, PRIVATE default |
| Candidate-boundary-first retrieval | ✅ `index/fts.py` `MATCH … AND tenant=? AND namespace=?`; scan over `objects(tenant, ns)` | ➕ predicate → `(tenant, authorized-space-set)`, still in-query |
| Fail-closed defaults | ✅ no ambient identity; header-authoritative scope (A-01) | ➕ visibility resolves to PRIVATE on missing/unknown |
| Append-only lineage for share/promote | ✅ open `Op` set; `_apply` generic; A-12 immutability | ➕ `knowledge_shared`/`knowledge_promoted` events (§3 fields) |
| Per-space index cost isolation | ❌ single shared `fts_idx` (OV-04 latency coupling) | ➕ partition per `(tenant, space)` |
| Labelled cross-space results | ⚠️ `why_returned`/`temporal_state` present; no space labels | ➕ `origin_space`/`visibility`/`why_accessible` (§12) |
| Capability to *grant* promotion | ❌ EPISTEMOS never grants; `_DEFAULT_CAPS` has no promote cap | policy in NOMOS/PDP (Q12); EPISTEMOS only enforces + logs |

---

## 11. Non-negotiables this design honours

- **Local-first & zero-egress preserved.** A standalone instance runs with only PRIVATE space, no
  federation, no account service — identical to today. Spaces above PRIVATE are opt-in; nothing
  auto-syncs, auto-uploads, or promotes without explicit authorization + policy + provenance +
  destination scope (assessment Q13/§25). The zero-egress gate is untouched.
- **PRIVATE by default, fail-closed.** PUBLIC is never inferred from absence of config (§4).
- **Four separate dimensions.** Source trust, contributor reputation, claim confidence, and
  evidence strength are never collapsed; visibility is a *fifth* axis and is likewise separate
  (§9). AGENT_OUTPUT ≠ VERIFIED FACT.
- **No mandatory central authority; no home-grown crypto.** Spaces are an in-process visibility
  field; cross-instance sharing is deferred to EPISTEMOS-06 signed packages using a **standard**
  crypto primitive.
- **EPISTEMOS enforces knowledge mechanics; it never grants capabilities.** Promotion authority is
  a PDP concern (NOMOS or other), optional and fail-closed (§6).
- **No "likes = truth".** Promotion is an authorized, logged, monotone lattice step — not a
  popularity signal.

---

## 12. Deliverables and classification (EPISTEMOS-04)

| Deliverable | Class | Backward-compatible? |
|-------------|-------|----------------------|
| `space` + `visibility` first-class `Envelope` fields, PRIVATE default | `FOUNDATIONAL_PRIMITIVE` | Yes — PRIVATE reproduces v0.2 |
| Visibility lattice enum (closed, ordered) | `FOUNDATIONAL_PRIMITIVE` | Yes |
| Retrieval predicate `(tenant, namespace)` → `(tenant, authorized-space-set)` | `FOUNDATIONAL_PRIMITIVE` | Yes — singleton set == today |
| `knowledge_shared` / `knowledge_promoted` ledger ops (§3 lineage fields) | `FOUNDATIONAL_PRIMITIVE` | Yes — additive `Op` names |
| Per-space index partitioning | `CURRENT_HARDENING (perf)` | Yes — result set unchanged |
| Cross-space labelled results (`origin_space`/`visibility`/`why_accessible`) | `FUTURE_CAPABILITY` | Yes — additive fields |
| PRIVATE→PUBLIC leak invariant + threat model | `FOUNDATIONAL_PRIMITIVE` | Yes (guards, not behaviour change) |
| Making `namespace` mean `space` | **REJECTED_DIRECTION** | — strands v0.2 semantics |
| Inferring PUBLIC from absent config | **REJECTED_DIRECTION** | — violates fail-closed |
| Mandatory central authority to promote/share | **REJECTED_DIRECTION** | — violates local-first (§13) |

**Bottom line.** Knowledge Spaces adds one orthogonal, ordered, fail-closed visibility axis on top
of the tenant isolation EPISTEMOS already enforces. Every piece is additive and defaults to the
v0.2 behaviour, so nothing ships in v0.3, the standalone/offline path is untouched, and the one
architectural gap the audit named (B-02: namespace is a partition, not an authorization boundary)
is closed by making visibility a first-class thing rather than an informal reading of namespace.
