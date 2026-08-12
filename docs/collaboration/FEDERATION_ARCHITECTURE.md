# EPISTEMOS — Federation Architecture (no central authority)

> **Status: DESIGN — DEFERRED to EPISTEMOS-06.** Nothing in this document ships in v0.3.
> Per the addendum (§28/§31) and `COLLABORATIVE_KNOWLEDGE_MODEL.md`, v0.3 ships only
> current-defect fixes and backward-compatible hardening. Federation transport, the signed
> Knowledge Package, subscriptions, and revocation-while-offline are all classified
> `FUTURE_CAPABILITY / EPISTEMOS-06` in the anchor's classification table. This is an
> architectural design that (a) shows federation is reachable **without sacrificing local-first /
> zero-egress**, and (b) proves it builds on properties that **already exist today** (with file
> evidence) rather than on new invented APIs.
>
> This document is the `FEDERATION_MODEL = DESIGNED` referenced in the anchor's mandated output
> block (addendum §32) and the companion to `KNOWLEDGE_PACKAGE_SPEC.md`. It is consistent with the
> anchor's Q10/Q12/Q13/Q15 decisions and does not restate the space/capability design (that is
> EPISTEMOS-04, `KNOWLEDGE_SPACES.md`).

---

## 0. Non-negotiables this design is bound by

These are copied from the anchor and the hard constraints; every section below is checked against
them.

| # | Invariant | Where enforced in this design |
|---|-----------|-------------------------------|
| 1 | **Local-first / zero-egress preserved.** Standalone/offline/single-agent keeps working unchanged. | Federation is an **opt-in adapter behind the storage/exchange port**; core makes no network calls (§1, §7). |
| 2 | **Additive & opt-in.** No auto-sync / telemetry / upload without explicit authorization + policy + provenance + destination-scope. | §5 (exchange is caller-initiated), §6 (subscription is opt-in and never auto-accepts). |
| 3 | **PRIVATE by default, fail-closed.** Never infer PUBLIC from absence of config. | Packages carry explicit visibility from the space lattice (EPISTEMOS-04); a package with no policy metadata is **refused**, not published (§4, §6). |
| 4 | **Four separate dimensions:** source trust ≠ contributor reputation ≠ claim confidence ≠ evidence strength. AGENT_OUTPUT ≠ VERIFIED FACT. | §4 keeps them separate primitives; §6 admits foreign packages only as **candidates**, never as believed facts. |
| 5 | **No mandatory central authority; no home-grown crypto; no "likes = truth".** | §2 (two topologies behind one port), §3 (standard detached signatures), §6/§8 (policy decides, reputation is input not authority). |
| 6 | **EPISTEMOS enforces knowledge mechanics; it never grants capabilities.** NOMOS is not mandatory. | §6 POLICY step calls out to a PDP (NOMOS *or* a local policy file *or* manual approval); the core only enforces verify/scope/candidate mechanics. |

---

## 1. "Shared knowledge ≠ shared storage" (addendum §13)

The load-bearing idea, straight from the anchor's Q15:

> *"The storage-port abstraction means 'shared knowledge ≠ shared storage': federation is
> instance-to-instance signed package exchange, not a shared database. Each consumer verifies and
> applies packages under its own policy … there is no global truth, only locally-accepted
> knowledge with preserved provenance."*

Federation does **not** mean two EPISTEMOS instances point at the same SQLite file, the same
server, or the same ledger. It means instance **A** produces a *self-contained, signed, verifiable
package* of a scoped slice of its knowledge, and instance **B** *receives, verifies, and decides*
whether to admit it — as candidates, under B's own policy, keeping B's ledger authoritative for B.

```
  ┌──────────────────────┐                                   ┌──────────────────────┐
  │   EPISTEMOS  A        │                                   │   EPISTEMOS  B        │
  │  (own ledger,         │   signed knowledge package        │  (own ledger,         │
  │   own store, own      │  ───────────────────────────────▶ │   own store, own      │
  │   policy, own clock)  │   (detached signature over the    │   policy, own clock)  │
  │                       │    canonical scoped export)       │                       │
  └──────────┬───────────┘                                   └───────────┬──────────┘
             │ export(principal)  ← EXISTS TODAY (A-11)                    │ import + verify_chain
             │ scope-limited, re-sealed, self-verifying                   │ ← EXISTS TODAY (A-01)
             ▼                                                            ▼
     A's authoritative state                                    B's authoritative state
     is NEVER mutated by B                                      is NEVER mutated by A
```

The exchanged unit is *data at rest in transit* — inert, like every ingested payload in the core
(`core/__init__.py` docstring: "ingested content is inert data … never dereferenced"). There is no
shared write path, no shared lock, no shared clock. This is what makes both topologies in §2
possible behind one abstraction.

---

## 2. Two topologies, one port — the core depends on neither

The anchor (Q12, Q15) puts federation *transport* in adapters, not the core. The core knows only an
**exchange port** — an interface for "hand me a package to admit" and "give me a package for this
scope". Concrete transports implement it. Two topologies are both valid, and **the core cannot tell
which one is in use**:

| | **Topology A — central shared service** | **Topology B — federated peer instances** |
|---|---|---|
| Shape | Many instances push/pull packages via one relay/registry | Instances exchange packages directly (or via gossip/queue) |
| Who is authoritative | **Each instance still owns its own ledger**; the service is a *relay of packages*, not a source of truth | Same — every peer owns its ledger |
| Central authority over truth | **None.** The service moves signed packages; it cannot forge, because it lacks issuer keys | None |
| Failure of the hub | Peers keep working standalone (zero-egress default) | N/A |
| Classification | Allowed **iff not mandatory** | Preferred default |
| Rejected variant | *Central SaaS as a **mandatory** dependency* → `REJECTED_DIRECTION` (anchor table; violates §13/§24) | — |

The distinction that keeps this honest: a central **relay of signed packages** is fine (it is a
transport adapter); a central **authority that decides what is true** is rejected. Truth is always
*locally accepted* (§6). The core's dependency is on the port, so swapping Topology A for B is an
adapter change with **zero core change** — this is the anchor's Q10 "irreversible decision avoided":
we never bake a central service into the core.

```
        ┌─────────────────────────────────────────────┐
        │              EPISTEMOS core                  │
        │   (invariants: verify, scope, candidate,     │
        │    bitemporal, ledger — makes NO net calls)  │
        └───────────────────┬─────────────────────────┘
                            │  ExchangePort (abstract)
          ┌─────────────────┼──────────────────────────┐
          ▼                 ▼                          ▼
   FileExchange       RelayExchange (Topology A)   PeerExchange (Topology B)
   (usb / disk /      (push/pull to a registry)    (direct A↔B, gossip, queue)
    air-gapped)       OPTIONAL, non-mandatory       OPTIONAL
          ▲
   the zero-egress-preserving default: a package is just a file you can carry
```

`FileExchange` matters: because a package is a self-verifying file, **federation works air-gapped**
— copy the file on a USB stick, import it on another machine. That is the strongest possible proof
that federation does not require a network, a service, or egress.

---

## 3. Standard signatures — no home-grown crypto (addendum §14)

The anchor rejects "bespoke/home-grown cryptography" (`REJECTED_DIRECTION`) and mandates a standard.
This design **names candidates and does not implement any** (implementation is EPISTEMOS-06).

**Mechanism: a detached signature over the canonical export.** The scoped export already produced by
`export(principal)` is serialized with the core's existing canonical JSON (`_util.canonical_json`,
already used by `seal()` in `ledger/__init__.py` so that hashing is deterministic). The issuer signs
the **bytes of that canonical serialization** (or, equivalently and more cheaply, the export's head
`entry_hash` plus a manifest hash). The signature is *detached*: it travels alongside the package,
never mutating the sealed ledger records. Verification is signature-check + `verify_chain` (§6).

Candidate standard schemes (**evaluate in EPISTEMOS-06; pick one, do not invent**):

| Candidate | Why it fits EPISTEMOS | Caveats to weigh |
|-----------|----------------------|------------------|
| **Ed25519** (RFC 8032, detached) | Small keys/sigs, fast, no parameter choices to get wrong, ubiquitous stdlib/`cryptography` support; matches "single-writer, offline-verifiable" | Key distribution/trust roots still needed (see below) |
| **RFC 8785 JCS + Ed25519** | Canonicalization is a *published standard*, reducing "our canonical JSON vs theirs" ambiguity across implementations | Must reconcile JCS with the core's existing `canonical_json`; pick one authority |
| **COSE / `COSE_Sign1`** (RFC 9052) | Standard envelope for detached signatures, good if packages cross language ecosystems | Heavier; more than a single-team deployment needs |
| **Sigstore / in-toto attestation** | Standard *provenance* attestation format; aligns with the PROV-O export also on the EPISTEMOS-06 roadmap | Bundles an ecosystem (transparency log) that may exceed local-first goals; keep optional |
| **minisign / signify** | Dead-simple detached signing of a file; excellent for `FileExchange`/air-gapped | Less structured metadata; fine as a floor, not the whole story |

**Trust-root question (explicitly deferred, not hand-waved):** a signature proves *who issued*, not
*whether to believe*. Key/issuer trust (pinned keys, a local allow-list of issuer public keys, or a
PKI/web-of-trust) is an **issuer-trust dimension**, kept separate from source trust and contributor
reputation (constraint #4). EPISTEMOS-06 must specify a **fail-closed default: an unknown issuer key
⇒ REFUSE** (never "unknown ⇒ trusted"), consistent with PRIVATE-by-default.

**What we will not do:** invent a signature construction, roll our own hash-then-XOR "signing", or
treat the existing hash chain *as if* it were a signature. The hash chain gives **tamper-evidence
within one ledger** (`ledger/__init__.py`: "tamper-evident, not immutable … a bare hash chain");
signatures give **cross-instance authenticity**. They are different jobs.

---

## 4. Federation primitives (the manifest)

A Knowledge Package = **the scoped export (payload) + a signed manifest (envelope)**. The anchor's
Q8 already says this: *"A Knowledge Package is that slice plus a manifest (issuer, subject, schema
version, content hashes, ledger anchor, signature, validity/expiry)."* The full field spec lives in
`KNOWLEDGE_PACKAGE_SPEC.md`; here is the primitive set and where each comes from today.

| Primitive | Meaning | Grounded in / new? |
|-----------|---------|--------------------|
| **issuer** | Which EPISTEMOS instance/key produced the package | New (identity of the *instance*, distinct from `Principal`); signed |
| **subject / scope** | The `(tenant, namespace[, space])` slice the package covers | `export(...)` already stamps `scope={tenant,namespace}` (`core.export`) |
| **schema version** | Model schema the payload conforms to | `SCHEMA_VERSION` already in every export (`model.SCHEMA_VERSION`) |
| **content hash(es)** | Per-record `content_hash` + a package digest over canonical bytes | `content_hash` exists per record (`ledger.content_hash`); package digest is new |
| **ledger anchor** | The head `entry_hash` (and count) of the re-sealed slice | `verify_chain(expected_head=, expected_count=)` already supports anchoring |
| **signature** | Detached standard signature over the canonical export/anchor | New (§3), standard scheme |
| **provenance** | owner (agent) / principal (human) / source (external) carried per object | Already three distinct roles in `Envelope` + `Source` (never collapsed) |
| **valid time + transaction time** | Bitemporal stamps per fact | `Fact.valid_from/valid_to`, `tx_from/tx_to` — already bitemporal |
| **expiry** | When the package's assertions should stop being auto-trusted | New manifest field (policy input, not a delete) |
| **revocation ref** | How the issuer publishes "I revoked claim X at T" | New (§7); represented as a transaction-time event, not a delete |
| **policy metadata** | Visibility class, license/usage, intended audience, destination-scope | New; **absence ⇒ REFUSE** (fail-closed, constraint #3) |

**The four dimensions stay four** (constraint #4): `source.trust` (source authority, already a
field), *contributor reputation* (EPISTEMOS-05, an evaluation input never an authority),
`confidence` (claim confidence, already a field), and *evidence strength* (claim-graph support,
EPISTEMOS-05). The manifest carries all of them as **separate** values; a consumer must never
collapse "signed by a reputable issuer" into "this claim is true" (that is exactly the
`likes = truth` anti-pattern the anchor rejects).

---

## 5. The exchange: `EPISTEMOS A --signed knowledge package--> EPISTEMOS B` (addendum §14)

```
A: build package                                B: admit package (§6 pipeline)
────────────────────                            ─────────────────────────────
principal_A  ──▶ export(principal_A)            receive bytes ──▶ verify signature (issuer key)
             (A-11: scope-limited,                            ──▶ verify_chain (A-01/A-02 machinery)
              re-sealed, self-verifying)                      ──▶ check scope vs declared subject
                     │                                        ──▶ POLICY (PDP / policy file / human)
                     ▼                                        ──▶ admit as CANDIDATES (never facts)
        canonical_json(export)                               ──▶ LOCAL ACCEPTANCE writes B's ledger
                     │                                              as NEW events, B-owned, provenance
             sign (Ed25519 detached)                               links back to issuer+package
                     │
             manifest{issuer, subject, schema,
             hashes, anchor, sig, validity,
             expiry, revocation-ref, policy}
                     │
                     ▼   ExchangePort.send()  (File / Relay / Peer — §2)
        ════════════ signed knowledge package ════════════▶  B
```

Key properties of the exchange:

- **A's export is already the right shape.** `export(principal)` (per A-11 fix) is *scope-limited*
  (only that principal's `(tenant, namespace)`), *re-sealed* into a fresh valid chain, and
  *self-verifying*. Federation adds a signature + manifest **around** it; it does not need a new
  export path. Evidence: `core.export`, `test_export_scope.py`.
- **B never trusts A's bytes as truth.** Verification proves *authenticity + integrity + scope*, not
  *veracity*. Admission is as candidates (§6).
- **Zero-egress on A's side too:** building and signing a package is a pure local computation;
  *sending* is the only networked act, and it is caller-initiated through the port — never automatic
  (constraint #2). An instance that never calls `send()` never egresses.

---

## 6. The subscription pipeline: RECEIVE → VERIFY → POLICY → CANDIDATE → LOCAL ACCEPTANCE (addendum §17)

**Never auto-accept as truth.** This is the heart of poisoning resistance and of "contribution ≠
truth" (anchor Q14). A subscription is opt-in; each stage can refuse and is fail-closed.

```
 RECEIVE ─▶ VERIFY ─▶ POLICY ─▶ CANDIDATE ─▶ LOCAL ACCEPTANCE
   │          │          │          │              │
   │          │          │          │              └─ writes B's OWN ledger as new events;
   │          │          │          │                 B-owned; provenance/derived_from links
   │          │          │          │                 back to issuer + package + original ids;
   │          │          │          │                 belief is B's, under B's confidence
   │          │          │          └─ admitted as Observation-like CLAIMS, not believed Facts;
   │          │          │             rival/contradictory claims COEXIST (contradiction is
   │          │          │             first-class — no silent overwrite)
   │          │          └─ PDP decides: NOMOS *or* a local policy file *or* manual human approval.
   │          │             EPISTEMOS enforces the mechanic; it never GRANTS the capability (§0/#6).
   │          │             Absent policy metadata ⇒ REFUSE (fail-closed).
   │          └─ signature valid (known issuer key)? chain verifies (verify_chain)? declared subject
   │             == payload scope (A-01 machinery: header is scope authority)? else REFUSE.
   └─ bytes arrive via ExchangePort (opt-in; a standalone instance subscribes to nothing).
```

Stage-by-stage, with what exists vs. what is deferred:

| Stage | What it does | Exists today | Deferred to |
|-------|--------------|--------------|-------------|
| RECEIVE | Bytes arrive via the port; opt-in, no auto-poll without config | port is new; **the "no network by default" property exists** | 06 (adapter) |
| VERIFY | Signature check; `verify_chain`; **scope match** (declared subject == sealed record scope) | `verify_chain` + `import_events`' scope authority (A-01) exist; signature is new | 06 (signature) |
| POLICY | External PDP / policy file / human decides admit/deny; fail-closed on missing policy | capability hooks exist (`Principal.require`, `_DEFAULT_CAPS`); **EPISTEMOS never grants** | 04 (capability model), 06 (wiring) |
| CANDIDATE | Admit as claims (Observation-shaped), not Facts; contradictions coexist | **Observation vs Fact separation exists** (`model.Observation`, `model.Fact`); contradiction is first-class (`Op.CONTRADICTION_RECORDED`) | 05 (claim graph / review) |
| LOCAL ACCEPTANCE | Promote a candidate to a B-owned believed fact via the normal command path | `assert_fact`/`supersede` with provenance links exist | 06 (promotion wiring) |

The crucial invariant, restated: **AGENT_OUTPUT ≠ VERIFIED FACT.** A package from a peer is, at best,
a well-attributed *Observation*. It becomes a *believed Fact* in B only when B's own policy promotes
it, through B's own ledger, under B's own confidence — exactly the ingestion pipeline the core
already models (`Observation → validation → candidate → accept`, anchor Q14).

---

## 7. Revocation / retraction while consumers are OFFLINE (addendum §18)

**No magic global delete.** The anchor is explicit (Q4, and A-12 makes it robust): federation
revocation is *"a consumer applies an issuer's revocation as a transaction-time event without
deleting history."* There is no cross-instance `DELETE`, because there is no shared store and no
central authority — and because deleting the past is exactly what A-12 forbids.

Representation: **"issuer revoked claim X at T"** is itself a **claim** the issuer publishes (in a
later package, or a revocation feed the manifest's `revocation-ref` points to). When consumer B
eventually receives it — *whenever B comes back online, in any order* — B applies it as a
**transaction-time event** against B's own copy:

```
 t0: A issues package P asserting X.  B (offline) has not seen it yet.
 t1: A revokes X.  A publishes "revoked X at t1" (a claim, signed, in a later package / feed).
 t2: B comes online, receives P and the revocation, in EITHER order.
     B applies them as events on B's ledger:
        - X admitted as a candidate/fact (B-owned), tx_from = when B recorded it
        - revocation recorded: B closes its belief in X (end_fact / retract), tx_to set ONCE
     B's history now shows: "B believed X from t2a to t2b, on A's authority, and stopped
     believing it because A revoked it."  Nothing is erased.
```

Why the bitemporal model makes this correct and offline-safe (cite Q4 / A-12):

- **Transaction time is append-only.** `_open_belief` refuses to re-close a closed belief
  (`ConflictError`), and `_apply` keeps the *first* close (`if obj.get("tx_to") is None:` in
  `core._apply`). So a revocation applied late cannot rewrite what B *is said to have believed*
  before it — `as_of(at_tx=T)` stays stable. This is precisely the A-12 guarantee.
- **Order independence.** Because valid time and transaction time are separate axes and belief is an
  open/closed interval (T-05: "believed now" = `tx_to is None`, clock-independent), B can receive the
  assertion and the revocation in any order and still reconstruct a coherent history — critical when
  A and B **do not share a clock**.
- **Consumer sovereignty.** B applies the revocation *under B's own policy*. B may honor it (close
  belief), or record it and keep its own contradicting belief (contradiction is first-class). The
  issuer cannot force a delete; it can only publish a claim. That is "no mandatory central
  authority" made concrete.

Evidence: `core._open_belief` / `core._apply` (append-only tx close), `test_belief_close_once.py`,
mutants `core_open_belief_guard` / `core_belief_reclose`; A-12 in `EPISTEMOS_V0_2_AUDIT.md`.

---

## 8. Forkable knowledge (addendum §16) — append-only + supersession already model it

Scenario: a **public base** of knowledge is forked by an org, which adds **local overrides**. Later,
**upstream updates** must **not erase** the org's local knowledge.

The anchor's insight (Q3): the ledger's append-only + supersession/derivation edges already express
forks and overrides *without any new merge machinery*. A fork is not a copy-and-mutate of a shared
database; it is B importing a base package and then **layering its own events on top**.

```
 PUBLIC BASE (issuer = upstream)              ORG FORK (in B's own ledger)
 ────────────────────────────                 ────────────────────────────
 fact:  X = "v1"  (from base package)   ─────▶ imported as a candidate, B-owned copy
                                               │
                                               ├─ B overrides locally:
                                               │    supersede(X) -> X' = "org-value"
                                               │    (X' .supersedes = (X,), X still in history)
                                               │
 upstream ships base v2:  X = "v2"     ─────▶  arrives as a NEW candidate on B's ledger
                                               │
                                               ▼
     B's POLICY decides the merge — it is NOT automatic:
       • keep local override  (X' wins; base v2 recorded but not promoted), OR
       • take upstream        (supersede X' with a fact derived_from base v2), OR
       • record contradiction (both coexist; contradiction is first-class)
     In every branch: NOTHING upstream sends can delete X' — upstream has no write
     access to B's ledger, and tx-time is append-only.  Local knowledge is safe by construction.
```

Why this needs **no new "merge" primitive** in the core:

- **Supersession is already lineage-preserving.** `supersede()` closes the old belief (kept, not
  deleted) and links `supersedes=(old,)`; `derived_from` records where a value came from
  (`core.supersede`, `core.correct_validity`). An "org override of a public fact" is just a
  supersede whose replacement is B-owned.
- **Upstream cannot reach into B.** There is no shared storage (§1); an upstream package is inert
  input. The only way base v2 affects B is through B's own POLICY promoting it — so **"upstream
  update must not erase local knowledge"** is guaranteed by the architecture, not by a merge rule.
- **`explain()` already walks arbitrary genealogy** (O(1) per node via the provenance index,
  ADR-022), so a forked object can always be traced back to the base package and issuer it came from.

Deferred pieces: the *fork/override UX*, a *base-package pinning* convention, and the claim-graph
`SUPPORTS/CONTRADICTS/SUPERSEDES/DERIVED_FROM` typing are EPISTEMOS-05/06. The *mechanics* they build
on (append-only ledger, supersession edges, derivation links, provenance walk) exist today.

---

## 9. What EXISTS TODAY vs. what is DEFERRED

Honest split (constraint: distinguish present-with-evidence from proposed). This is the foundation
federation builds on — the anchor's Q8 ("the foundation shipped in EPISTEMOS-03").

**EXISTS TODAY (with file evidence):**

| Capability federation reuses | Evidence |
|------------------------------|----------|
| Scope-limited, **re-sealed, self-verifying** export per principal | `core.export(principal)`; `test_export_scope.py`; A-11 |
| Import that **verifies the chain** and **refuses scope mismatch** (header is scope authority) | `core.import_events`, `core._guard_payload_scope`; A-01/A-02; `test_import_scope.py` |
| Import **refuses a non-empty target** (no silent interleave) | `core.import_events` (`ConflictError`) |
| Import **refuses a chainless export** under `verify=True` | `core._carries_chain` / `import_events` |
| Tamper-evident hash chain with **external anchoring** (head + count) | `ledger.verify_chain(expected_head=, expected_count=)` |
| **Bitemporal** facts; append-only transaction time (offline-safe revocation) | `model.Fact`; `core._open_belief`/`_apply`; A-12; `test_belief_close_once.py` |
| **Observation (claim) vs Fact (belief)** separation; first-class contradiction | `model.Observation`, `model.Fact`, `Op.CONTRADICTION_RECORDED` |
| Three distinct provenance roles (owner/principal/source) + **source.trust** as its own field | `model.Envelope`, `model.Source.trust` |
| Supersession/derivation lineage; genealogy walk | `core.supersede`/`correct_validity`; `explain()` |
| **Zero-egress**: core makes no network calls (verified across lifecycle incl. index path) | `core` docstring; audit "Negative results" |
| Capability **hooks** (`require`, `guard_owner`, `_DEFAULT_CAPS`) — the seam a PDP attaches to | `identity.Principal`, `_DEFAULT_CAPS` |

**DEFERRED (proposed; not implemented):**

| Deferred piece | Milestone |
|----------------|-----------|
| `space` / `visibility` first-class field + fail-closed default (packages need it) | EPISTEMOS-04 |
| Capability-based authorization / PDP wiring for the POLICY step | EPISTEMOS-04 (+ 06 wiring) |
| Knowledge Package **manifest + standard signature** | EPISTEMOS-06 (`KNOWLEDGE_PACKAGE_SPEC.md`) |
| The **ExchangePort** + transports (File / Relay / Peer) | EPISTEMOS-06 |
| Subscription pipeline (receive→verify→policy→candidate→accept) | EPISTEMOS-06 |
| Revocation feed / `revocation-ref` convention | EPISTEMOS-06 |
| Issuer-key trust roots (pinned keys / allow-list / PKI), fail-closed default | EPISTEMOS-06 |
| Fork/override UX + base-package pinning | EPISTEMOS-05/06 |
| Contributor reputation as an **evaluation input** (never authority) | EPISTEMOS-05/07 |
| Sybil / laundering / replay defenses (content hashes + anchors as inputs) | EPISTEMOS-07 (`THREAT_MODEL.md`) |
| PROV-O / PROV-JSON export of provenance | EPISTEMOS-06 |

**REJECTED (from the anchor's classification table):** central SaaS as a *mandatory* dependency;
home-grown cryptography; `likes = truth` / social scoring as authority; collapsing source-trust and
contributor-reputation.

---

## 10. Zero-egress preservation — restated as an acceptance gate

Federation must be *invisible* to a standalone instance. The design guarantees this because:

1. The core depends only on the **ExchangePort abstraction**, which a standalone build simply does
   not instantiate — same pattern as the vector backend already being an optional port (anchor Q12).
2. Every networked act (`send`, `subscribe`, `pull`) is **caller-initiated**; there is no auto-sync,
   no auto-poll, no telemetry (constraint #2).
3. Building/signing/verifying a package is pure local computation; a `FileExchange` proves federation
   works with **no network at all** (§2).
4. The anchor's gates stay first-class: `STANDALONE_WITHOUT_NETWORK` and `ZERO_EGRESS_DEFAULT` (Q13).

Proposed EPISTEMOS-06 acceptance gates (adversarially testable, in the audit's red-then-green style):

- `FED_OPT_IN_ONLY` — with no exchange adapter configured, **no** network syscall occurs across the
  full lifecycle (extend the existing zero-egress probe to the federation path).
- `FED_FAIL_CLOSED_UNKNOWN_ISSUER` — a package signed by an unknown key is **refused**, not admitted.
- `FED_NO_AUTO_TRUTH` — an admitted package appears as candidates only; no believed Fact exists in B
  until an explicit local-acceptance/promotion event.
- `FED_SCOPE_AUTHORITY` — a package whose declared subject ≠ payload scope is refused (reuse the A-01
  header-is-authority machinery).
- `FED_REVOKE_APPEND_ONLY` — applying a revocation never moves a prior `tx_to`; `as_of(at_tx=T)`
  before the revocation is unchanged (reuse the A-12 guard).
- `FED_LOCAL_KNOWLEDGE_SAFE` — an upstream update never deletes or overwrites a B-owned override.

---

## 11. Summary

Federation in EPISTEMOS is **instance-to-instance exchange of signed, self-verifying Knowledge
Packages**, admitted only as **candidates** under each consumer's **own policy**, with revocation
modeled as **append-only transaction-time claims** and forks modeled as **local supersession over an
imported base** — all behind **one storage/exchange port** that supports a central-relay topology or
a peer topology **without the core depending on either**, and **without a mandatory central
authority**. The hard parts (scoped re-sealed export, chain verification with scope authority,
bitemporal append-only revocation, claim/belief separation, zero-egress) **already exist and were
hardened, not compromised, by EPISTEMOS-03**. The missing parts (manifest + standard signature, the
exchange port and transports, the subscription pipeline, issuer-key trust) are **strictly additive**
and **deferred to EPISTEMOS-06**, behind **fail-closed, opt-in** defaults so that a standalone,
offline, single-agent EPISTEMOS keeps behaving exactly as it does today.

**Mandated output line (anchor §32):**
`FEDERATION_MODEL = DESIGNED` — instance-to-instance signed Knowledge Packages; central OR peer
topology behind one port; no mandatory central authority — EPISTEMOS-06. See this document and
`KNOWLEDGE_PACKAGE_SPEC.md`.
