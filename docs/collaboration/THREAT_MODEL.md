# EPISTEMOS — Collaborative / Federated Threat Model (EPISTEMOS-04…07)

> **Status: DESIGN — DEFERRED.** Nothing in this document ships in v0.3. Per the owner
> addendum (§28/§31) and `COLLABORATIVE_KNOWLEDGE_MODEL.md`, v0.3 carries **only** current-defect
> fixes and backward-compatible hardening. Every collaborative primitive named here is classified
> `FOUNDATIONAL_PRIMITIVE` or `FUTURE_CAPABILITY` and is scheduled to a named milestone
> (**EPISTEMOS-04** spaces + capabilities, **-05** claims/contributor/reputation, **-06** federation
> packages, **-07** anti-manipulation). This model is the security half of that roadmap: it says what
> must be true *before* any collaborative surface is allowed to exist.
>
> **This document is DISTINCT from `docs/security/THREAT_MODEL.md`** (the single-instance model,
> S1–S50). That model governs one running instance: caller↔engine auth, tenant isolation, the ledger
> tamper battery, zero-egress, ingestion-as-inert-data. It is **referenced, not duplicated** here.
> This document adds only the boundaries that appear when knowledge crosses a **visibility** or an
> **instance** edge — boundaries that do not exist in v0.3 because those edges do not exist yet.

---

## 1. What changes when knowledge becomes collaborative

The single-instance model has exactly two hard boundaries: `tenant` (isolation) and `namespace`
(partition inside a tenant). Audit finding **B-02** established the load-bearing truth this whole
model rests on:

> `namespace` is a **partition within** the tenant isolation boundary, **not** a per-agent or
> per-visibility authorization boundary. (`EPISTEMOS_V0_2_AUDIT.md`, B-02 → FOUNDATIONAL.)

Collaboration introduces two boundaries the code does **not** yet express:

| New boundary | Definition | Introduced by | Today |
|---|---|---|---|
| **Visibility / space edge** | PRIVATE → TEAM → ORG → COMMUNITY → PUBLIC, a *lattice* orthogonal to tenant | EPISTEMOS-04 | Does not exist. `Principal.scope = (tenant, namespace)` is unordered (`identity/__init__.py`). |
| **Instance / federation edge** | knowledge crossing from one sovereign EPISTEMOS to another as a signed package | EPISTEMOS-06 | Does not exist. `export()`/`import_events()` are file-level, not networked, and make no calls. |

Because neither edge exists in v0.3, **there is no PUBLIC to leak into and no peer to poison from
today.** That is not an accident to be preserved by vigilance — it is the fail-closed baseline. The
threats below are the ones that appear the moment we add the edges, and the design rule is that each
edge must ship *with* its defense, never before it.

### Trust boundaries added (beyond S-model boundaries 1–4)

```
  5. Space edge (PRIVATE ↔ shared)   — promotion is the ONLY legal crossing; it must require
                                        capability + policy + provenance + destination-scope.
  6. Instance edge (peer ↔ peer)     — every inbound package is HOSTILE until verified;
                                        RECEIVE → VERIFY → POLICY → CANDIDATE → LOCAL ACCEPT.
  7. Contributor ↔ space             — a contributor is attributable but NOT authoritative;
                                        a claim is a claim, never an accepted belief.
```

Design invariants inherited unchanged from v0.3 (proven, not re-litigated here): fail-closed
identity (`require_principal`), tamper-evident hash-chained ledger (`ledger/verify_chain`),
bitemporal immutability of the past (**A-12**), ingested content is **inert data** (§19.8), and
**zero-egress by default** — collaborative mode is *additive and opt-in*; no auto-sync, telemetry,
or upload without explicit authorization + policy + provenance + destination scope
(`COLLABORATIVE_KNOWLEDGE_MODEL.md` Q13, gates `STANDALONE_WITHOUT_NETWORK` / `ZERO_EGRESS_DEFAULT`).

---

## 2. PRIORITY THREAT 1 — `PRIVATE_TO_PUBLIC_LEAK` (P0, addendum §10)

**Property to defend:** private knowledge must **never** become visible outside its authorized
scope without an explicit, authorized, policy-checked, provenance-bearing, destination-scoped
contribution. Absence of configuration must **never** be read as PUBLIC — PRIVATE is the fail-closed
default at every boundary. This is the single P0 the addendum will not compromise on.

The leak surface decomposes into six vectors. For each, the honest question is: *did EPISTEMOS-03
already close this at the `(tenant, namespace)` boundary, or is it structurally new at the space
edge and therefore deferred to EPISTEMOS-04?*

### 2.1 Leak-vector enumeration

| # | Leak vector | Mechanism | Status at `(tenant,namespace)` today | Deferred work at space edge |
|---|---|---|---|---|
| L1 | **Implicit visibility default** | An object with no explicit visibility is treated as shareable | **CLOSED (baseline).** No `visibility` field exists; every read/write is scoped to exact `(tenant, namespace)` and fail-closed (`guard_scope`, `require_principal`). There is no shared tier to default into. | EPISTEMOS-04: `visibility` becomes first-class and **MUST default PRIVATE**; unknown/absent ⇒ PRIVATE, never inferred PUBLIC. (Rejected direction: making `namespace` silently mean `space`.) |
| L2 | **Promotion without authorization** | A share/promote operation moves an object up the lattice with no capability/policy check | **N/A today — no promotion primitive exists**, so it cannot be misused. | EPISTEMOS-04/05: `knowledge_shared`/`knowledge_promoted` ledger events (additive, Q3) gated by a **capability** (`promote`), a **policy decision** (NOMOS or another PDP — EPISTEMOS *enforces*, never *grants*, Q12), recorded **provenance** (`promoted_by`, `source_space`→`destination_space`), and an explicit **destination scope**. Fail-closed: missing any of the four ⇒ refuse. |
| L3 | **Retrieval exposing out-of-scope candidates / metadata / timing** | Search retrieves globally then filters, leaking existence, ranking, or latency of unseen content | **CLOSED (Q6, P0).** Retrieval is **candidate-boundary-first**: FTS query is `… MATCH ? AND tenant = ? AND namespace = ?` (filtered in SQLite, not post-hoc in Python); the scan iterates `store.objects(tenant, namespace)`. No global-retrieve-then-filter path exists. Mutant `idx_search_tenant_leak` is killed. | EPISTEMOS-04: extend the boundary predicate from `(tenant, namespace)` to `(tenant, authorized-space-set)` — the *same* candidate-first shape, wider predicate. Timing side-channel (OV-04: shared FTS table couples latency across scopes) closed by **per-space index partitioning**. Gate: **`CROSS_SPACE_RETRIEVAL_LEAK = 0`**. |
| L4 | **Export crossing scope** | An export dumps more than the caller's scope | **CLOSED (A-11, A-01, B-01).** `export(principal)` is scope-limited and re-sealed into a fresh valid chain; `scope="all"` requires `admin`; REST fails closed on a `None` principal (`rest_none_principal`); import takes scope from the **sealed record header**, not attacker-controlled payload (`core_import_scope_authority`), so a crafted export cannot write into another scope. `test_export_scope.py`, `test_import_scope.py`. | EPISTEMOS-06: a **Knowledge Package** is that same scoped, re-sealed slice **plus** a signed manifest (issuer, subject, schema version, content hashes, ledger anchor, validity/expiry). The package boundary must re-assert the space predicate: a package may carry only objects at-or-below the authorized destination visibility. |
| L5 | **Source-pointer dereference across scope** | Reading a fact's `source`/`trust` reaches an object in another scope, disclosing its URI or authority | **CLOSED (B-06).** All four deref sites (`search`, `explain`, both trust lookups) require the source to share the object's `(tenant, namespace)`; a dangling/cross-scope pointer yields trust `0.0` and no URI (`_trust_lookup`, `retrieval_source_scope`). EPISTEMOS also **never dereferences a source URI as a fetch target** — it is an identifier (`add_source` note). | EPISTEMOS-04: the same scope check widens to the authorized-space-set; a shared fact whose `source` lives in a PRIVATE space must not expose that source across the space edge (deref returns no-authority, not the private URI). |
| L6 | **Health / existence oracles** | `get()`, `health()`, or error-code differences reveal that out-of-scope content exists | **CLOSED (B-01, B-06/B-07).** `get()` returns `None` for both absent and cross-scope ids (no existence oracle); `explain()` raises identically for both; `_ref_in_scope` never confirms existence across a boundary; scoped `health()` returns only the scope's `event_count` and **no** global `head_hash`. `test_boundary_hardening.py`. | EPISTEMOS-04: preserve the *indistinguishability* property across the space edge — a principal must not distinguish "no such object in any space I may see" from "exists in a space I may not see", including via timing (L3) and via error taxonomy. |

### 2.2 Reading of the table

Five of six vectors (L1, L3, L4, L5, L6) are **already closed at the boundary that exists today**,
by EPISTEMOS-03 defect fixes that were shipped as current-defect work — this is exactly the
"private must never leak" foundation the addendum's P0 demanded, delivered early. The sixth (L2,
promotion) is **not a gap** — it is a surface that *does not exist yet* and must be born gated.

The single new architectural requirement is that **every one of these boundary checks must be
re-expressed against the space lattice, not silently inherit the tenant/namespace check.** The
danger is subtle: widening `(tenant, namespace)` to `(tenant, authorized-space-set)` must keep the
predicate **authoritative and candidate-first** (L3) — a regression that filters *after* ranking, or
that resolves a space membership from attacker-controlled payload rather than the sealed header (the
A-01 failure mode, one lattice level up), reopens the leak.

**Governing gate:** `CROSS_SPACE_RETRIEVAL_LEAK = 0`, plus `PRIVATE_TO_PUBLIC_LEAK = 0` enforced by
red-then-green tests at each of L1–L6's space-edge equivalent before EPISTEMOS-04 may freeze.

---

## 3. PRIORITY THREAT 2 — Poisoning / manipulation set (P0, addendum §19)

**Property to defend:** a contributor can inject *claims*, never *truth*. `AGENT_OUTPUT ≠ VERIFIED
FACT`. The four dimensions — **source trust** (`Source.trust`), **contributor reputation** (new,
EPISTEMOS-05), **claim confidence** (`Envelope.confidence`), **evidence strength** — stay separate
and are never collapsed into a single score, and none of them is *authority*. Reputation is an
**input** to evaluation, never a grant; there is **no `likes = truth`** (rejected direction, §7).

The defenses layer on properties EPISTEMOS **already has**: the claim/belief split
(`Observation` = raw claim vs `Fact` = bitemporal belief), contradiction as a first-class coexisting
edge (rivals are never silently overwritten), and an **attributable, tamper-evident ledger** (every
contribution is signed into the hash chain with `actor`/`principal`, verifiable by `verify_chain`).

### 3.1 Threat enumeration

| # | Threat | Defense principle | Exists today | Deferred |
|---|---|---|---|---|
| P1 | **Sybil contributors** (many fake identities inflate a claim) | Contribution ≠ truth; per-domain reputation as *input, not authority*; count of contributors never decides belief | Claim/belief split present; ledger attributes every write to `actor`/`principal`. No contributor identity, so no Sybil surface reachable. | EPISTEMOS-05 contributor identity + EPISTEMOS-07 Sybil resistance (reputation as bounded input, identity cost, never "N confirmations ⇒ true"). |
| P2 | **Coordinated false confirmation** (colluders raise a false fact's confidence) | `confirm()` is **corroboration only** — it may not *lower* a rival (B-03: `delta < 0` rejected, `core_confirm_negative_delta`); confidence is a mutable annotation, **not** belief and **not** bitemporally authoritative (T-03) | `confirm` weaponization removed today; confidence never flips the *believed* interval (which is tx-time, A-12). | EPISTEMOS-07: cross-contributor confirmation weighted by *independent* reputation, capped so collusion cannot manufacture authority. |
| P3 | **Reputation farming** (grind reputation, then abuse it) | Reputation is **per-domain** and **input-not-authority**; no global karma; no `likes = truth` | Nothing to farm today (no reputation). | EPISTEMOS-05/07: reputation is domain-scoped, decays, and is only ever one term in evaluation — never a capability grant (that is a PDP concern, Q12). |
| P4 | **Evidence laundering** (cite a fabricated/borrowed source to look grounded) | Provenance must **resolve to a real source in scope**; cross-scope source forgery already blocked | **Partly present:** A-01 (scope authority on import) + B-06 (scoped source deref) stop cross-scope source forgery today; `derived_from`/`evidence`/`source` refs must resolve in-scope (`_ref_in_scope`). | EPISTEMOS-06: package manifests bind evidence to **content hashes + ledger anchor**, so a laundered citation across the instance edge fails verification. |
| P5 | **Source impersonation** (claim to be an authoritative origin) | `owner`/`principal`/`source` are **three distinct roles** and must not be collapsed (Q5); source is an inert identifier, never dereferenced | Three roles distinct today (`Envelope` + `Source`); source URI never fetched. | EPISTEMOS-06: **standard** signature over packages (no home-grown crypto, §14) authenticates the issuing instance; impersonation across the edge requires a forged signature. |
| P6 | **Mass contribution spam** (flood the store/candidate set) | Bounded ingestion; contribution admitted as candidate, not belief | Size/shape caps present today (`EngineLimits`: `max_text`, `max_document_bytes`, `max_metadata_bytes`, `max_json_depth`; annotation lists bounded to 256, B-06). | EPISTEMOS-07: per-contributor quotas/rate limits at the contribution boundary; candidate admission cost. |
| P7 | **Knowledge poisoning** (inject a false belief directly) | Ingest yields a **claim** (`Observation`), not a belief; belief is separate; **contradiction is first-class** (rivals coexist, no silent overwrite); ledger makes it attributable + reversible | **Present:** `Observation` vs `Fact`; `contradict()` records coexisting rival edges; `retract`/`supersede` preserve history; A-12 keeps the past immutable. | EPISTEMOS-05: explicit claim→validation→candidate→accept **review pipeline** and claim graph (SUPPORTS/CONTRADICTS/SUPERSEDES/DERIVED_FROM). |
| P8 | **Prompt injection inside evidence** (ingested text carries instructions) | Ingested content is **INERT DATA** — never executed, never dereferenced, never fed to a model by the core | **Present and tested:** `test_stored_prompt_injection_is_data`, `test_injection_payload_is_inert` (MCP), `test_unicode_query_injection_is_inert`, `test_sql_injection_payload_is_inert`; core makes no model/network calls (NullModelProvider runs the whole core). | EPISTEMOS-05/06: property must be **restated for federation** — a package's payload is inert data on receipt; any downstream component that *interprets* it (a model, a PDP) is outside the core and must treat it as untrusted. |
| P9 | **Malicious graph relationships** (poison the entity graph / expansion DoS) | Refs must resolve in-scope; traversal is **bounded**; in-place rewrites are **owner-guarded** | **Present:** `add_relation` requires both endpoints in scope; `query_graph` caps `max_hops` + node budget (`max_graph_nodes`) — expansion-DoS defense; `merge_entities`/`split_entity` carry `guard_owner` (B-04). | EPISTEMOS-04: relationship endpoints must respect the space lattice — no edge may bridge a PRIVATE object into a shared space without promotion (L2). |
| P10 | **Replay of revoked knowledge** (re-inject something already retracted) | **Content-hash + ledger-anchor**; bitemporal revocation applies **offline** without deleting history | **Present:** `source_hash`/content hashes (`hash_obj`) identify payloads; the ledger anchors order; A-12 + T-05 make "believed now" the open-interval, clock-independent test, so a consumer applies an issuer's revocation as a tx-time event across instances that share no clock (Q4). | EPISTEMOS-06: package manifest carries validity/expiry + ledger anchor; a replayed package is detected by anchor + content hash and refused at VERIFY. |
| P11 | **Cross-space inference** (aggregate visible signals to infer private content) | Candidate-boundary-first retrieval (L3); no cross-scope metadata/timing signal | **Present at tenant/namespace:** L3/L5/L6 closed; no aggregation channel across the boundary today. | EPISTEMOS-04: per-space index partitioning removes the latency channel (OV-04); aggregate/count queries must be scoped so they cannot be differenced to infer hidden membership. |
| P12 | **Metadata leakage** (existence, counts, activity of hidden content) | Scoped counts, no global head, no existence oracle | **Closed (B-01, B-06/B-07):** scoped `health()` hides global `head_hash`; `get()` non-oracle; annotation caps prevent unbounded metadata growth. | EPISTEMOS-04: the same non-oracle guarantees must hold across the space edge, including error-taxonomy and timing indistinguishability (L6). |

### 3.2 What holds today vs what is deferred

**Structurally present today (proven, load-bearing):** the claim/belief split (P7), contradiction-first
coexistence (P7), the attributable tamper-evident ledger (P1/P4/P10), ingested content as inert data
(P8, tested), the four-dimension separation of trust/confidence (P2, kept distinct in
`temporal._rank_key`), bounded traversal + owner guards (P9), scoped non-oracle reads (P11/P12), and
offline-safe bitemporal revocation (P10, A-12/T-05).

**Deferred (do not exist, must arrive gated):** contributor identity and reputation as
input-not-authority (P1/P2/P3 → EPISTEMOS-05/07), contribution quotas (P6 → 07), the claim-review
pipeline and claim graph (P7 → 05), standard-crypto signed packages with content-hash/anchor
binding (P4/P5/P10 → 06), and every "restate across the space/instance edge" obligation (P8/P9/P11/P12
→ 04/06).

The through-line: **no deferred defense is a promise to bolt security on later.** Each is the
non-negotiable precondition of the surface it guards — the surface may not ship without it.

---

## 4. Gate table

A milestone may **not** freeze until its gates are `PASS` with a red-then-green test (and a mutation
where a boundary is critical), matching the EPISTEMOS-03 discipline.

| Gate | Statement | Owner milestone | Baseline today |
|---|---|---|---|
| `PRIVATE_TO_PUBLIC_LEAK = 0` | No object crosses a visibility edge without capability + policy + provenance + destination-scope (L1–L6) | EPISTEMOS-04 | L1,L3,L4,L5,L6 closed at tenant/namespace; L2 surface absent |
| `CROSS_SPACE_RETRIEVAL_LEAK = 0` | Retrieval never exposes existence/metadata/ranking/**timing** of out-of-scope candidates; predicate is candidate-first + authoritative | EPISTEMOS-04 | Closed at `(tenant,namespace)` (Q6); timing coupling OV-04 open |
| `VISIBILITY_DEFAULT = PRIVATE` | Absent/unknown visibility ⇒ PRIVATE; PUBLIC is never inferred from absence | EPISTEMOS-04 | Enforced implicitly (no shared tier exists) |
| `PROMOTION_FAIL_CLOSED = TRUE` | Missing any of {capability, policy, provenance, destination-scope} ⇒ refuse | EPISTEMOS-04/05 | N/A (no promotion primitive) |
| `CLAIM_NOT_TRUTH = TRUE` | Contribution enters as claim/candidate; belief requires validation; `AGENT_OUTPUT ≠ FACT` | EPISTEMOS-05 | Present (`Observation` vs `Fact`) |
| `DIMENSIONS_SEPARATE = 4` | trust / reputation / confidence / evidence never collapsed to one score | EPISTEMOS-05 | 3 present + distinct; reputation deferred |
| `REPUTATION_IS_INPUT_NOT_AUTHORITY = TRUE` | Reputation never grants a capability; per-domain; no `likes = truth` | EPISTEMOS-05/07 | N/A (no reputation) |
| `INGESTED_CONTENT_INERT = TRUE` | Payloads (local and packaged) are data; never executed/dereferenced by the core | EPISTEMOS-06 (restate) | **PASS today**, tested (§19.8) |
| `FEDERATION_REPLAY_BLOCKED = TRUE` | Content-hash + ledger-anchor + validity/expiry refuse replayed/revoked packages | EPISTEMOS-06 | Primitives present (hash, anchor, A-12); package layer deferred |
| `STANDARD_CRYPTO_ONLY = TRUE` | Signatures use a vetted standard behind a port; no home-grown crypto | EPISTEMOS-06 | N/A (no signing yet) |
| `ZERO_EGRESS_DEFAULT = TRUE` | No sync/upload/telemetry without explicit authorization + policy + provenance + destination-scope | all | **PASS today** (Q13) |
| `STANDALONE_WITHOUT_NETWORK = TRUE` | Offline single-agent instance behaves exactly as v0.3 | all | **PASS today** (Q13) |
| `NO_MANDATORY_CENTRAL_AUTHORITY = TRUE` | Federation is peer-capable; core depends on no central service or PDP | EPISTEMOS-06 | Design-affirmed (Q15); rejected direction otherwise |

---

## 5. Cross-references

- `docs/collaboration/COLLABORATIVE_KNOWLEDGE_MODEL.md` — the anchor assessment; this threat model
  realizes its `PRIVATE_TO_PUBLIC_LEAK_MODEL` and `POISONING_THREAT_MODEL` output lines and its
  classification table (§31). Consistent with Q4, Q5, Q6, Q12, Q13, Q14, Q15.
- `docs/security/THREAT_MODEL.md` — the single-instance model (S1–S50). All caller↔engine,
  tenant-isolation, ledger-tamper, and inert-data properties this document builds on live there; not
  duplicated.
- `docs/audit/EPISTEMOS_V0_2_AUDIT.md` — findings this model stands on: **A-01** (import scope
  authority), **A-11** (scoped re-sealed export), **A-12** (immutable past → offline revocation),
  **B-01** (fail-closed principal, get/health non-oracle), **B-02** (namespace ≠ authorization
  boundary), **B-03** (confirm corroboration-only), **B-04** (owner guards), **B-06** (scoped source
  deref), **OV-04** (shared-index timing coupling).
- Source evidence: `src/epistemos/model/__init__.py` (`Observation`/`Fact`, `Source.trust`,
  `Envelope.confidence`), `src/epistemos/identity/__init__.py` (`Principal`, `_DEFAULT_CAPS`,
  guards), `src/epistemos/ledger/__init__.py` (`verify_chain`), `src/epistemos/core/__init__.py`
  (`export`, `import_events`, `_apply`, `_trust_lookup`, `EngineLimits`).

## 6. Direct answer

The P0 leak surface is **five-sixths already closed** at the only boundary that exists in v0.3, and
the sixth vector is a surface that must be *born* gated rather than a hole to be patched. The
poisoning surface rests on properties EPISTEMOS **already owns** — claim ≠ truth, contradiction-first,
an attributable tamper-evident ledger, inert ingested data, and four never-collapsed dimensions — with
the genuinely new defenses (contributor reputation as input-not-authority, signed replay-proof
packages, contribution quotas) deferred to the milestones that introduce the surfaces they guard.
No collaborative edge ships without its defense; PRIVATE stays the fail-closed default; zero-egress
and standalone operation are preserved by construction.
