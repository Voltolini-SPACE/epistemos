# EPISTEMOS — Collaborative / Federated Knowledge Infrastructure Assessment

> Owner addendum to EPISTEMOS-03. This is an **architectural assessment and roadmap**, not an
> implementation. Per addendum §28/§31 nothing here ships in v0.3 except (a) fixes to current
> defects and (b) backward-compatible hardening with adversarial tests. Everything collaborative is
> classified and deferred.

**The question the addendum demands an answer to:**

> *Can EPISTEMOS evolve into a collaborative / federated knowledge infrastructure without sacrificing
> its sovereign / local-first model?*

**Answer: YES — and the v0.2 architecture is already shaped for it, but three current properties
must change first (all backward-compatible), and one invariant must be added.** This is sustained by
architecture and by the EPISTEMOS-03 evidence below, not by opinion.

The short form: EPISTEMOS already separates *claim* from *belief* (Observation vs Fact), keeps
*source trust* separate from *confidence*, records an append-only hash-chained genealogy, filters
retrieval at the authorized candidate boundary, and is zero-egress by construction. Those are exactly
the hard parts of collaborative knowledge. What it does **not** yet have is (1) a visibility/space
lattice distinct from the tenant boundary, (2) capability-based (not role-based) authorization, and
(3) a `PRIVATE → PUBLIC` leak invariant enforced at promotion/federation boundaries. Those are
additive.

---

## Principle alignment (addendum §1, §30)

`PRIVATE BY DEFAULT` — already true: unknown tenant/namespace/source/schema/integrity ⇒ refuse
(fail-closed), and EPISTEMOS-03 closed the holes where it wasn't (A-01, A-11, B-06).
`SHAREABLE BY PERMISSION` — needs the capability model (EPISTEMOS-04).
`COLLECTIVE BY VERIFICATION` — the ledger + provenance + contradiction model already makes
"contribution ≠ truth" representable; needs the claim-review pipeline (EPISTEMOS-05).
`FEDERATED BY DESIGN` — the storage-port abstraction and the re-sealable export make this reachable
without a central service (EPISTEMOS-06).

---

## The 15 audit questions, answered with evidence

**Q1. Does the current tenant model support Knowledge Spaces?**
Partially. `Principal(tenant, agent, namespace)` gives a two-level scope: `tenant` is the hard
isolation boundary; `namespace` partitions within it. A space lattice (PRIVATE/TEAM/ORG/COMMUNITY/
PUBLIC) is a **visibility ordering**, which the current model does *not* express — namespaces are
unordered peers with no cross-visibility. So spaces need a new dimension, not a rename of namespace.
*Evidence:* `identity/__init__.py` — `scope = (tenant, namespace)`, no ordering; all store queries
filter by exact `(tenant, namespace)`.

**Q2. Should tenant and space be different entities?**
**Yes.** Tenant is *ownership/isolation* (whose data this is). Space is *visibility* (who may see it,
along a lattice). Collapsing them (as v0.2 effectively does with namespace) is exactly what produced
audit finding B-02: namespace was informally treated as agent-privacy but is only a partition inside
the tenant boundary. EPISTEMOS-04 introduces `space` (with an explicit `visibility` on every object)
as a first-class field orthogonal to tenant.

**Q3. Can the ledger represent share/promotion/review/dispute without losing genealogy?**
**Yes, natively.** The ledger is append-only and hash-chained; supersession/derivation/contradiction
are already first-class edges preserved forever (verified: A-12 fix guarantees the past cannot be
rewritten). New event types (`knowledge_shared`, `knowledge_promoted`, `claim_reviewed`,
`claim_disputed`) are additive events carrying `source_space`/`destination_space`/`promoted_by` — the
existing `_apply` projection pattern extends to them, and `explain()` (now O(1), ADR-022) already
walks arbitrary derivation genealogy. *Evidence:* `ledger/__init__.py` `Op` is an open set of event
names; `provenance/explain` walks `derived_from`/`supersedes`/`contradicts` generically.

**Q4. Does the temporal model support federated knowledge correctly?**
**Yes, and this is a strength.** Bitemporality answers "what did the system believe at T" and "when
was it true", which federation needs for revocation-while-offline (§18): a consumer applies an
issuer's revocation as a *transaction-time* event without deleting history. The EPISTEMOS-03 fix
(T-05: "believed now" = open interval, clock-independent) is what makes this robust across
instances that do not share a clock. *Evidence:* `temporal/believed()`; `test_import_scope` shows a
foreign-stamped ledger imports and reconstructs correctly.

**Q5. Can provenance represent human + agent + external source?**
**Yes, three distinct roles already exist and must not be collapsed (addendum §5/§6):** `owner`
(the *agent* that ingested), `principal` (the *human/service* on whose behalf), and `source` (the
*external origin*, with its own `trust`). The model already distinguishes WHO CONTRIBUTED (owner/
principal) from WHERE IT CAME FROM (source). EPISTEMOS-05 adds a `contributor` identity for shared
spaces and, crucially, keeps *contributor reputation* a fourth, separate dimension from *source
trust* — the audit (B-06) proved these are already independent (source trust is dereferenced
scope-safely and never blended into confidence). *Evidence:* `model.Envelope` (owner, principal,
source, confidence) + `Source.trust`; `temporal._rank_key` keeps trust and confidence as distinct
tuple components.

**Q6. Can retrieval apply visibility before candidate exposure?**
**Yes — the architecture is already candidate-boundary-first, which is P0 (§11).** Both retrievers
scope at the SQL/`objects()` boundary *before* ranking: the FTS index query is
`... MATCH ? AND tenant = ? AND namespace = ?` (filter in SQLite, not "retrieve globally then
filter in Python"), and the scan iterates `store.objects(tenant, namespace)`. There is no
global-retrieve-then-filter path that could leak existence/metadata/timing of out-of-scope content.
EPISTEMOS-04 extends the boundary predicate from `(tenant, namespace)` to
`(tenant, authorized-space-set)`. *Evidence:* `index/fts.py::search`, ADR-017; the tenant-filter
mutant `idx_search_tenant_leak` is killed. `CROSS_SPACE_RETRIEVAL_LEAK` reduces to keeping this
predicate authoritative.

**Q7. Can FTS5 be partitioned / filtered safely per space?**
**Yes for correctness today; a performance caveat for scale.** The tenant/namespace columns already
filter safely at the query boundary (no leak — verified). BUT the shared FTS table means MATCH
resolves across all rows before the tenant filter, so one space's corpus inflates another's search
*latency* (audit OV-04 — a cost coupling, **not** a leak). EPISTEMOS-04 should partition the index
per space (separate FTS tables or a partitioned column) so cost is isolated too. *Evidence:*
OV-04 measured neighbour-tenant latency inflation; the result set is always correctly scoped.

**Q8. Can export/import evolve into Knowledge Packages?**
**Yes — the foundation shipped in EPISTEMOS-03.** `export(principal)` already produces a
**scope-limited, re-sealed, self-verifying** event slice (A-11 fix). A Knowledge Package is that
slice plus a manifest (issuer, subject, schema version, content hashes, ledger anchor, signature,
validity/expiry). Import already verifies the chain, refuses non-empty targets, and (A-01 fix)
refuses payload/scope mismatch. The package spec (`KNOWLEDGE_PACKAGE_SPEC.md`) is the export format +
a signed manifest envelope. *Evidence:* `core.export`/`import_events`; `test_export_scope`.

**Q9. What must change before a public API 1.0?**
Four things, all identified by EPISTEMOS-03 or this assessment: (a) the capability model must be real
(enforcement by capability, not by the default-caps set — §4); (b) `space`/`visibility` must be a
first-class field with a fail-closed default; (c) the `PRIVATE → PUBLIC` leak invariant must be
enforced and tested; (d) the API surface (§23) must be reviewed as *capability requirements*, not
frozen names. None of these are reversible-if-wrong-cheaply, so they precede 1.0.

**Q10. Which decisions would be irreversible if implemented now?**
Making `namespace` mean "space" (would strand the tenant/namespace semantics); baking a *central*
federation service into the core (violates local-first §13/§24); choosing a bespoke signature/crypto
scheme (§14 — must use a standard); collapsing source-trust and contributor-reputation into one
score (§6/§7). This assessment **avoids all four** by deferring them to designed ADRs.

**Q11. Which primitives belong in the core?**
`space`/`visibility` field + fail-closed default; capability tokens + enforcement hook; the
`PRIVATE→PUBLIC` invariant; the claim/evidence/belief distinction (already present); the re-sealable
scoped export (already present). These are *knowledge invariants* the core must own regardless of any
external authority — the same reasoning that keeps tenant isolation in the core, not NOMOS.

**Q12. Which belong in adapters / plugins?**
Federation transport (HTTP/gossip/queue); the signature/verification backend (a standard, behind a
port); reputation computation; the policy engine that *decides* promotion (NOMOS or another PDP —
EPISTEMOS enforces the mechanics, never grants the capability, §22); vector/embedding backends
(already a port, ADR-020). The core stays a control-plane of invariants; adapters are the execution
plane.

**Q13. How is local-first / zero-egress preserved?**
By construction and by test. The core makes no network calls (zero-egress gate, re-verified across
the full lifecycle including the index path). Collaborative mode is **additive**: an instance runs
standalone with no space beyond PRIVATE, no federation, no account service. Federation is an opt-in
adapter that never auto-syncs, auto-uploads, or contributes without explicit authorization + policy +
provenance + destination scope (§25). Gates `STANDALONE_WITHOUT_NETWORK` and `ZERO_EGRESS_DEFAULT`
stay first-class.

**Q14. How is knowledge poisoning prevented?**
Layered, and mostly by properties EPISTEMOS already has: contribution is a *claim*, not truth
(Observation→validation→candidate→accept); belief is separate from ingest; the ledger makes every
contribution attributable and tamper-evident; contradiction is first-class (rival claims coexist, no
silent overwrite). What EPISTEMOS-07 adds: Sybil/coordinated-confirmation resistance (per-domain
reputation as *input* to evaluation, never authority — §7), evidence-laundering detection (provenance
must resolve to a real source, and A-01/B-06 already stop cross-scope source forgery), and
replay-of-revoked-knowledge defense (content hashes + ledger anchors). The full model is
`THREAT_MODEL.md`.

**Q15. How is federation enabled without a central authority?**
The storage-port abstraction means "shared knowledge ≠ shared storage" (§13): federation is
instance-to-instance signed *package* exchange, not a shared database. Each consumer verifies and
applies packages under its own policy (RECEIVE→VERIFY→POLICY→CANDIDATE→LOCAL ACCEPTANCE, §17) — there
is no global truth, only locally-accepted knowledge with preserved provenance. Two topologies (central
service *or* peer instances) are both supported behind the same package/port design; the core depends
on neither.

---

## What EPISTEMOS-03 changed *now* in service of this vision

The addendum's P0 is "private must never leak". EPISTEMOS-03 closed the actual leaks that existed in
v0.2 — this is the collaborative vision's foundation, delivered as current-defect fixes:

- **A-01** cross-tenant injection via crafted import → fixed (header is the scope authority).
- **A-11** cross-tenant export leak over REST → fixed (scoped, re-sealed export).
- **B-06** cross-scope source-pointer dereference → fixed (scope-checked at all sites).
- **B-01** REST fail-closed on a None principal; get() existence-oracle closed; health() no longer
  leaks global counts cross-tenant.
- **A-12** the past cannot be rewritten (prerequisite for offline-safe federated revocation).

Everything else in this document is **DEFERRED** and classified below.

---

## Classification (addendum §31)

| Item | Class | Milestone |
|------|-------|-----------|
| Cross-tenant leak fixes (A-01, A-11, B-06, B-01) | CURRENT_DEFECT | **Done (v0.3)** |
| Bitemporal immutability (A-12) | CURRENT_DEFECT | **Done (v0.3)** |
| `space` / `visibility` first-class field + fail-closed default | FOUNDATIONAL_PRIMITIVE | EPISTEMOS-04 |
| Capability-based authorization (enforce by capability) | FOUNDATIONAL_PRIMITIVE | EPISTEMOS-04 |
| `PRIVATE → PUBLIC` leak invariant + threat model | FOUNDATIONAL_PRIMITIVE | EPISTEMOS-04 |
| Per-space index partitioning (OV-04) | CURRENT_HARDENING (perf) | EPISTEMOS-04 |
| Observability / structured metrics | FUTURE_CAPABILITY | EPISTEMOS-04 |
| Contributor identity (distinct from owner/principal/source) | FOUNDATIONAL_PRIMITIVE | EPISTEMOS-05 |
| Claim graph (SUPPORTS/CONTRADICTS/SUPERSEDES/DERIVED_FROM) | FUTURE_CAPABILITY | EPISTEMOS-05 |
| Generational confidence (T-03: confidence not yet versioned) | FUTURE_CAPABILITY | EPISTEMOS-05 |
| Per-domain reputation as evaluation input (never authority) | FUTURE_CAPABILITY | EPISTEMOS-05/07 |
| Knowledge Package (manifest + signature over the scoped export) | FUTURE_CAPABILITY | EPISTEMOS-06 |
| Federation transport + signed exchange (standard crypto) | FUTURE_CAPABILITY | EPISTEMOS-06 |
| PROV-O / PROV-JSON export | FUTURE_CAPABILITY | EPISTEMOS-06 |
| Ledger snapshot / compaction (tamper-evident) | FUTURE_CAPABILITY | EPISTEMOS-06 |
| Subscriptions (receive→verify→policy→candidate→accept) | FUTURE_CAPABILITY | EPISTEMOS-06 |
| Sybil / poisoning / anti-manipulation | FUTURE_CAPABILITY | EPISTEMOS-07 |
| Central SaaS as a *mandatory* dependency | REJECTED_DIRECTION | — (violates §13/§24) |
| Bespoke/home-grown cryptography | REJECTED_DIRECTION | — (§14: use a standard) |
| `likes = truth` / social scoring as authority | REJECTED_DIRECTION | — (§7) |
| Collapsing source-trust and contributor-reputation | REJECTED_DIRECTION | — (§6) |
| Making `namespace` silently mean `space` | REJECTED_DIRECTION | — (strands v0.2 semantics) |

---

## Mandated output block (addendum §32)

```
COLLABORATIVE_ARCHITECTURE_ASSESSED = TRUE
KNOWLEDGE_SPACES_MODEL      = DESIGNED (space + visibility lattice, orthogonal to tenant; fail-closed
                              PRIVATE default) — EPISTEMOS-04. See KNOWLEDGE_SPACES.md
CAPABILITY_MODEL            = DESIGNED (explicit capability tokens; roles = capability sets;
                              enforcement by capability/policy, not role) — EPISTEMOS-04
CLAIM_MODEL                = PARTIAL_PRESENT (Observation=claim vs Fact=belief already separate;
                              claim graph + review pipeline designed) — EPISTEMOS-05. See
                              CLAIMS_EVIDENCE_TRUST.md
PROVENANCE_MODEL           = PRESENT_AND_SUFFICIENT (owner/agent, principal/human, source/external
                              distinct today; contributor identity + reputation added as separate
                              dimensions) — extend in EPISTEMOS-05
FEDERATION_MODEL           = DESIGNED (instance-to-instance signed Knowledge Packages; central OR
                              peer topology behind one port; no mandatory central authority) —
                              EPISTEMOS-06. See FEDERATION_ARCHITECTURE.md, KNOWLEDGE_PACKAGE_SPEC.md
PRIVATE_TO_PUBLIC_LEAK_MODEL = DESIGNED + PARTIALLY_ENFORCED (candidate-boundary-first retrieval and
                              scoped export already prevent implicit leaks; A-01/A-11/B-06 fixed the
                              actual holes; the promotion/federation leak invariant is EPISTEMOS-04)
POISONING_THREAT_MODEL     = DESIGNED (claim≠truth, contradiction-first, attributable ledger today;
                              Sybil/laundering/replay defenses designed) — EPISTEMOS-07. See
                              THREAT_MODEL.md

CORE_CHANGES_REQUIRED_NOW  = NONE beyond the EPISTEMOS-03 defect fixes already shipped. The
                              collaborative primitives are all additive and must NOT be rushed into
                              v0.3 (addendum §28).
CORE_CHANGES_DEFERRED      = space/visibility field; capability enforcement; PRIVATE→PUBLIC invariant;
                              contributor identity; claim graph; generational confidence; knowledge
                              package manifest+signature; federation transport; per-space index
                              partitioning; observability; snapshot/compaction; PROV export.

EPISTEMOS_04_RECOMMENDATION = KNOWLEDGE SPACES + CAPABILITY MODEL. Rationale: it is the prerequisite
                              for every other collaborative capability (nothing can be shared safely
                              until visibility and authorization are first-class and fail-closed), it
                              is backward-compatible (PRIVATE default reproduces today's behaviour),
                              and it directly closes the one architectural gap the audit found
                              (B-02: namespace is a partition, not an authorization boundary).
```

## Direct answer

**Can EPISTEMOS evolve into a collaborative / federated knowledge infrastructure without sacrificing
its sovereign / local-first model? — Yes.** The properties that are hard to retrofit (claim/belief
separation, tamper-evident genealogy, fail-closed scoping, candidate-boundary retrieval,
zero-egress, bitemporal revocation) are already present and were *hardened*, not compromised, by
EPISTEMOS-03. The properties that are missing (space lattice, capability authorization, the
PRIVATE→PUBLIC invariant, federation packaging) are strictly **additive** and can be introduced
behind fail-closed defaults so that a standalone, offline, single-agent EPISTEMOS keeps behaving
exactly as it does today. The one thing that would sacrifice the model — a mandatory central service —
is explicitly rejected; federation is peer-capable by the storage-port design. The path is
EPISTEMOS-04 → 07, each a designed, adversarially-testable step, with no irreversible decision taken
prematurely.
