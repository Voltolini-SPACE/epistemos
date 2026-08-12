# EPISTEMOS — Knowledge Package Specification (EPISTEMOS-06)

> **Status: DESIGN — DEFERRED to EPISTEMOS-06.** Nothing in this document ships in v0.3.
> Per the collaborative addendum (§28/§31) and `COLLABORATIVE_KNOWLEDGE_MODEL.md`, v0.3 ships
> **only** current-defect fixes. This spec describes a *future* portable unit. Its **foundation**
> — the scoped, re-sealed, self-verifying export and the fail-closed import — **already shipped in
> EPISTEMOS-03** (A-11, A-01); only the manifest envelope (signing/verification, anchoring,
> revocation) is new here.
>
> Anchor: this document is the concrete realization of `FEDERATION_MODEL = DESIGNED` and the
> "Knowledge Package (manifest + signature over the scoped export)" row in the addendum §31
> classification table. It answers audit question **Q8** ("Can export/import evolve into Knowledge
> Packages?" — *Yes; the foundation shipped in EPISTEMOS-03*).

---

## 1. What a Knowledge Package is

A **Knowledge Package** is the portable unit of federation. It is exactly two parts:

```
Knowledge Package  =  (1) the EXISTING scoped, re-sealed export   [ships today — A-11]
                    +  (2) a signed MANIFEST envelope             [new — EPISTEMOS-06]
```

Part (1) is not invented here. `core.Engine.export(principal)` already produces a
**scope-limited, re-sealed, self-verifying** slice of the ledger (see `core/__init__.py:1348`).
Part (2) wraps that slice with an *out-of-band-verifiable* header: who issued it, what scope it
covers, the content hashes it commits to, the ledger anchor a verifier must reproduce, a standard
signature, validity/expiry, and non-authoritative policy hints.

The design principle throughout: **the package carries knowledge, never authority.** A consumer
VERIFIES a package and then applies it *under its own policy* (RECEIVE → VERIFY → POLICY →
CANDIDATE → LOCAL ACCEPTANCE, per `COLLABORATIVE_KNOWLEDGE_MODEL.md` §17). Importing a package is
never "accept these as facts"; the four dimensions stay separate — **source trust ≠ contributor
reputation ≠ claim confidence ≠ evidence strength**, and `AGENT_OUTPUT ≠ VERIFIED FACT`.

### Non-goals (rejected directions, addendum §31)

- **No mandatory central authority.** A package is exchanged instance-to-instance; a hub is one
  optional topology, not a dependency.
- **No home-grown cryptography.** Signing uses a *standard* scheme behind a port (§7 below).
- **No "likes = truth".** No field in this format grants belief or ranks by popularity.
- **No specific database.** The body is events, not rows; a consumer on any `Store` backend can
  import it (§15 of the anchor: "No specific database required").

---

## 2. What exists today vs. what is proposed

| Concern | Exists today (with evidence) | Proposed (EPISTEMOS-06) |
|---|---|---|
| Scoped slice of a tenant/namespace | `export(principal)` filters to `(tenant, namespace)` and **re-seals** into a fresh valid chain (`resealed: true`) — `core/__init__.py:1394-1419` | unchanged; becomes the package **body** |
| Self-verifying body | export events carry `seq/content_hash/prev_hash/entry_hash`; `verify_chain` re-derives them — `ledger/__init__.py:141` | unchanged |
| Fail-closed import | `import_events` refuses a non-empty target, refuses a body with no chain, refuses schema mismatch without `migrate` — `core/__init__.py:1421` | unchanged; gains a manifest pre-check |
| Scope-authority on projection | `_apply` takes `(tenant, namespace)` from the **sealed header**, not payload (A-01) — `core/__init__.py:283` | unchanged; the invariant the package relies on |
| External anchor detection | `verify_integrity(expected_count=, expected_head=)` → `verify_chain(...)` catches tail-truncation / full rewrite — `core/__init__.py:1294`, `ledger/__init__.py:177-180` | manifest **carries** `expected_head`/`count`; VERIFY feeds them in |
| Manifest (issuer/subject/hashes/anchor) | — | **new** |
| Signature over the manifest (standard crypto) | — | **new** (port + adapter) |
| Revocation application (offline) | bitemporal close is append-only (A-12); `tx_to` never moves | **new**: apply an issuer revocation as a transaction-time event |

Everything in the left column is real and tested. Everything in the right column is deferred.

---

## 3. The body — the existing export, unchanged

The package body **is** the dict returned by `export(principal)`. Its shape (verbatim from
`core/__init__.py`, `EXPORT_FORMAT = "epistemos-events"`, `SCHEMA_VERSION = 1`):

```
{
  "format":        "epistemos-events",     # EXPORT_FORMAT
  "schema_version": 1,                      # model.SCHEMA_VERSION
  "exported_at":   "<iso8601>",
  "event_count":   <int>,
  "events":        [ <event>, ... ],
  "scope":         {"tenant": "<t>", "namespace": "<ns>"},
  "resealed":      true                     # scoped exports are always re-sealed
}
```

Each element of `events[]` is a re-sealed ledger record (`_record_to_dict`, `core/__init__.py:1599`):

```
{
  "seq":          <int>,        # 1-based, contiguous in the re-sealed chain
  "ts":           "<iso8601>",  # event time (world clock of the issuing instance)
  "op":           "<Op>",       # e.g. "fact_asserted" (ledger.Op — an OPEN set)
  "tenant":       "<t>",        # header scope authority (NOT the payload's)
  "namespace":    "<ns>",
  "actor":        "<agent>",    # owner — the AGENT that ingested
  "principal":    "<human|null>", # the human/service on whose behalf (may be null)
  "payload":      { ... },      # op-specific; inert data, never executed/dereferenced
  "content_hash": "<sha256>",   # hash_obj({op, payload})
  "prev_hash":    "<sha256>",   # GENESIS_HASH ("0"*64) for seq 1
  "entry_hash":   "<sha256>"    # commits to header incl. content_hash + prev_hash
}
```

Because a scoped export is **re-sealed** (`resealed: true`), `prev_hash` of `seq=1` is
`GENESIS_HASH` and the chain is internally self-consistent — it verifies and re-imports, but its
`entry_hash` values are *new* and differ from the source instance's live ledger. This is by design
(filtering a hash chain breaks linkage; re-sealing restores it). The manifest's ledger anchor
(§4) therefore anchors to the **re-sealed** head, i.e. the head a verifier will independently
recompute from the body — not to the issuer's private live head.

> Provenance note (addendum §5/§6): `actor`/`owner`, `principal`/human, and the `source` pointer
> inside a fact payload (with its own `Source.trust`) are **three distinct roles** and are carried
> as-is. The package never collapses them, and never blends `Source.trust` into a fact's
> `confidence`. A future `contributor` identity and reputation are a *fourth/fifth* dimension added
> at the manifest/space layer (EPISTEMOS-05), never inside the sealed body.

---

## 4. The manifest — the new envelope (addendum §15)

The manifest is a small, signable header. It commits to the body by hash and to the ledger by
anchor, so a verifier can prove *provenance of the package itself* out of band from the events.

| Field | Type | Meaning | Fail-closed rule |
|---|---|---|---|
| `manifest_version` | int | Manifest format version (independent of body `schema_version`) | unknown ⇒ REFUSE |
| `issuer` | string | Stable identity of the issuing instance/key (e.g. key id / DID) | must match the signing key (§7) |
| `subject` | object | What is packaged: `{tenant, namespace, space}` | see visibility below |
| `space` | string | Visibility space of the contents (EPISTEMOS-04 lattice) | **absent ⇒ PRIVATE**, never PUBLIC |
| `body_schema_version` | int | Mirrors body `schema_version` (`= 1` today) | mismatch with body ⇒ REFUSE |
| `body_format` | string | Mirrors body `format` (`"epistemos-events"`) | mismatch ⇒ REFUSE |
| `content_hashes` | object | `{ "body_sha256": "<hex>", "event_count": <int> }` — hash over canonical body | recompute mismatch ⇒ REFUSE |
| `ledger_anchor` | object | `{ "expected_head": "<entry_hash of last event>", "expected_count": <int> }` | fed to `verify_chain` (§5) |
| `signature` | object | `{ "alg": "ed25519", "key_id": "...", "sig": "<base64>" }` — standard scheme, over canonical manifest-sans-signature | invalid/absent ⇒ REFUSE |
| `valid_time` | object? | Optional world-time window the package asserts (`{from, to}`) | informational; not authority |
| `transaction_time` | string | When the package was issued (issuer tx clock) | recorded on import as provenance |
| `expiry` | string? | Instant after which VERIFY must fail | past ⇒ REFUSE (fail-closed) |
| `revocation` | object? | `{ "revokes": ["<pkg_id|entry_hash>", ...], "reason": "..." }` | applied as tx-time close (§6) |
| `policy_hints` | object? | **Non-authoritative** suggestions (e.g. `suggested_space`, `min_source_trust`) | consumer policy MAY ignore |
| `package_id` | string | Content-addressed id of this package (hash of manifest incl. signature) | used by revocation/dedup |

**Signature scope.** The signature covers the canonicalized manifest *excluding* the `signature`
object itself, and the manifest commits to the body via `content_hashes.body_sha256`. Thus one
signature transitively authenticates the entire package (manifest + body). No bespoke construction:
the signing/verifying primitive is a **standard** (Ed25519 is the reference default) behind a
`Signer`/`Verifier` port (§7) — consistent with the addendum's rejection of home-grown crypto.

**Visibility is fail-closed.** `space`/visibility follows the EPISTEMOS-04 rule: absence is
**PRIVATE**, never inferred PUBLIC. A package with no `space` is treated as the most restrictive
class and may only be imported into a PRIVATE space unless the consumer's policy explicitly
promotes it. This is the packaging-layer expression of the `PRIVATE → PUBLIC` leak invariant.

---

## 5. Concrete example — a package with a 2-event body

Illustrative (hashes truncated for readability; real values are 64-hex SHA-256). The body is
exactly what `export(principal)` emits for a tenant `acme` / namespace `research` slice containing
one source and one fact.

```json
{
  "package": "epistemos-knowledge-package",
  "package_version": 1,
  "manifest": {
    "manifest_version": 1,
    "issuer": "did:key:z6Mk…acme-node-1",
    "subject": { "tenant": "acme", "namespace": "research", "space": "TEAM" },
    "space": "TEAM",
    "body_format": "epistemos-events",
    "body_schema_version": 1,
    "content_hashes": {
      "body_sha256": "b91c…f0a2",
      "event_count": 2
    },
    "ledger_anchor": {
      "expected_head": "7e3d…c4a1",
      "expected_count": 2
    },
    "valid_time": { "from": "2026-01-01T00:00:00Z", "to": null },
    "transaction_time": "2026-08-11T14:03:22Z",
    "expiry": "2026-11-11T00:00:00Z",
    "revocation": null,
    "policy_hints": { "min_source_trust": 0.5, "suggested_space": "TEAM" },
    "package_id": "pkg_9f2c…8801",
    "signature": {
      "alg": "ed25519",
      "key_id": "acme-node-1/2026",
      "sig": "MEUCIQ…base64…"
    }
  },
  "body": {
    "format": "epistemos-events",
    "schema_version": 1,
    "exported_at": "2026-08-11T14:03:22Z",
    "event_count": 2,
    "scope": { "tenant": "acme", "namespace": "research" },
    "resealed": true,
    "events": [
      {
        "seq": 1,
        "ts": "2026-03-02T09:15:00Z",
        "op": "source_added",
        "tenant": "acme",
        "namespace": "research",
        "actor": "ingestor-agent",
        "principal": "alice",
        "payload": {
          "id": "src_01", "kind": "source", "tenant": "acme", "namespace": "research",
          "owner": "ingestor-agent", "created_at": "2026-03-02T09:15:00Z",
          "schema_version": 1, "uri": "urn:doi:10.1000/xyz",
          "source_kind": "paper", "trust": 0.7, "metadata": {}
        },
        "content_hash": "a1b2…9f",
        "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
        "entry_hash": "1c4e…22"
      },
      {
        "seq": 2,
        "ts": "2026-03-02T09:16:10Z",
        "op": "fact_asserted",
        "tenant": "acme",
        "namespace": "research",
        "actor": "ingestor-agent",
        "principal": "alice",
        "payload": {
          "id": "fact_01", "kind": "fact", "tenant": "acme", "namespace": "research",
          "owner": "ingestor-agent", "created_at": "2026-03-02T09:16:10Z",
          "schema_version": 1,
          "subject": "compound-x", "predicate": "inhibits", "object": "enzyme-y",
          "valid_from": null, "valid_to": null,
          "tx_from": "2026-03-02T09:16:10Z", "tx_to": null,
          "status": "asserted", "memory_class": "semantic",
          "source": "src_01", "confidence": 0.9, "derived_from": [],
          "metadata": {}
        },
        "content_hash": "d4f5…07",
        "prev_hash": "1c4e…22",
        "entry_hash": "7e3d…c4a1"
      }
    ]
  }
}
```

Note the invariants visible in the example:

- `body.events[1].entry_hash` (`7e3d…c4a1`) **equals** `manifest.ledger_anchor.expected_head`, and
  `event_count == expected_count == 2`. VERIFY recomputes the chain from the body and checks this
  equality — the manifest cannot claim an anchor the body does not produce.
- `events[0].prev_hash` is `GENESIS_HASH` because the scoped export was re-sealed (`resealed: true`).
- The fact keeps `source: "src_01"` and `confidence: 0.9` **separately** from the source's
  `trust: 0.7`. The package never merges them.
- `space: "TEAM"` is explicit; had it been absent, VERIFY would treat the contents as **PRIVATE**.

---

## 6. Operations (addendum §15) and their mapping to what exists

Six operations define the package lifecycle. Three are (almost) entirely present today; three are
new. **None require a specific database.**

| Op | Purpose | Maps to (today) | New in EPISTEMOS-06 |
|---|---|---|---|
| **EXPORT** | Produce a package from a scope | `export(principal)` → body (A-11) | wrap body in a signed manifest |
| **IMPORT** | Ingest a verified package into an empty engine | `import_events(payload, verify=True)` (fail-closed) | manifest pre-check before body import |
| **SHARE** | Hand a package to a peer/hub | — (transport is an adapter, §7) | out-of-core transport port |
| **VERIFY** | Prove a package is authentic & intact | `verify_integrity(expected_head=, expected_count=)` → `verify_chain` | manifest signature + content-hash + expiry checks |
| **REVOKE** | Withdraw previously shared knowledge | append-only bitemporal close (A-12) exists as a *mechanism* | apply an issuer revocation as a tx-time event |
| **SYNC** | Repeated EXPORT→SHARE→IMPORT under policy | building blocks exist | opt-in, never automatic (see below) |

### 6.1 EXPORT

`EXPORT(principal, space) → package`. Today `export(principal)` already yields the scoped, re-sealed
body. EPISTEMOS-06 computes `content_hashes.body_sha256` over the canonicalized body, sets
`ledger_anchor` to the body's last `entry_hash` and `event_count`, attaches issuer/subject/space/
validity, and **signs** the manifest. No live-ledger secret leaves the instance; only the re-sealed
slice does. `scope="all"` (whole-store) is **not** a valid package source over any remote boundary —
it requires `admin` and is for the in-process operator only (`core/__init__.py:1378`).

### 6.2 IMPORT

`IMPORT(package) → count`. The body flows into the **existing** `import_events`, which already:
refuses a non-empty target (`ConflictError`, "import target store is not empty"); refuses a body
with no verifiable chain unless `verify=False` (then it is explicitly *unverified, trusted input*,
not tamper-evident history); and refuses a schema mismatch unless `migrate=True`. Critically,
`_apply` derives `(tenant, namespace)` from the **sealed header**, not the payload (A-01), and
`_guard_payload_scope` raises `IntegrityError` on any payload/header scope mismatch — so a crafted
package with an internally-valid chain still cannot project into another scope. EPISTEMOS-06 adds a
**manifest pre-check** (VERIFY, §6.4) that must pass *before* the body is handed to `import_events`,
and applies the consumer's space/visibility policy (fail-closed PRIVATE) to decide the destination
space. Import remains an "into an EMPTY engine" operation at the ledger level; multi-package
accumulation is a consumer-side concern (candidate staging → local acceptance), not a silent
interleave.

### 6.3 SHARE

`SHARE(package, destination)`. Transport (HTTP, gossip, queue, file hand-off) lives **outside the
core**, behind a port (§7). The core neither opens sockets nor auto-uploads. SHARE is always an
explicit, authorized act with an explicit destination scope — never a side effect of EXPORT.

### 6.4 VERIFY (the gate)

`VERIFY(package) → ok | reject`. This is the security-critical operation. It **must** check all
seven, fail-closed on the first failure:

1. **format** — `body.format == "epistemos-events"` and `manifest.body_format` matches; else
   `SchemaError` (mirrors `import_events`' `"unrecognized export format"`).
2. **schema** — `body.schema_version == manifest.body_schema_version`, and engine supports it (`= 1`)
   or `migrate=True` was requested.
3. **chain integrity** — `verify_chain(body.events)` re-derives every `content_hash`/`entry_hash`
   and linkage (detects payload edits, header edits, seq gaps, reorders, prev-hash swaps).
4. **manifest signature** — verify `signature.sig` over the canonical manifest-sans-signature with
   the issuer's key via the `Verifier` port (standard alg, e.g. Ed25519).
5. **content-hash match** — recompute `body_sha256` over the canonical body; must equal
   `content_hashes.body_sha256` and `event_count`.
6. **ledger anchor** — call `verify_integrity(expected_head=manifest.ledger_anchor.expected_head,
   expected_count=…)`; the body's recomputed head/count must match (catches tail-truncation and
   full re-chained rewrite — `ledger/__init__.py:177-180`).
7. **scope / visibility** — `body.scope` must equal `manifest.subject.{tenant,namespace}`;
   `space` present (else PRIVATE); `expiry` not past; and the consumer's `PRIVATE → PUBLIC`
   invariant satisfied for the intended destination.

Checks 3 and 6 are **already implemented** (`verify_chain`, `verify_integrity`); 1–2 mirror
`import_events`' existing guards; 4–5 and the visibility half of 7 are the **new** work.

### 6.5 REVOKE

`REVOKE(package_or_entries, reason)`. Federation needs revocation-while-offline. EPISTEMOS already
has the *mechanism*: transaction time is append-only (A-12) and a belief is closed by appending a
`fact_superseded`/`fact_retracted` event that sets `tx_to` — the past is never rewritten. A consumer
that receives a signed revocation manifest applies it as a **local transaction-time event** against
the imported facts (by content hash / entry hash / `package_id`), so `as_of(at_tx=before)` still
answers with the old belief and `as_of(at_tx=after)` reflects the revocation. Nothing is deleted;
history is preserved; no shared clock is required (T-05: "believed now" is the open interval). The
revocation is *the issuer's claim*; the consumer applies it under policy, never as external
authority over local state.

### 6.6 SYNC

`SYNC` is repeated EXPORT → SHARE → IMPORT under policy. It is **opt-in and never automatic**
(addendum §13/§25): no auto-sync, no telemetry, no upload without explicit authorization + policy +
provenance + destination scope. A standalone, offline, single-agent EPISTEMOS performs **zero**
SYNC and behaves exactly as v0.2/v0.3 does. The gates `STANDALONE_WITHOUT_NETWORK` and
`ZERO_EGRESS_DEFAULT` remain first-class and must stay green with this feature present but unused.

---

## 7. Where the pieces live (core vs. adapter)

Consistent with `COLLABORATIVE_KNOWLEDGE_MODEL.md` Q11/Q12 — the core owns *knowledge invariants*,
adapters own *execution*:

| Component | Home | Rationale |
|---|---|---|
| Body production (`export`) & consumption (`import_events`) | **core** (exists) | invariants: scope authority, chain verification, fail-closed import |
| Manifest schema + VERIFY sequencing | **core** | the package's integrity/visibility invariants must not depend on any transport |
| `Signer` / `Verifier` port | **core interface**, **adapter impl** | standard crypto (Ed25519) behind a port; no home-grown scheme in core |
| Transport (HTTP/gossip/queue/file) | **adapter** | zero-egress core makes no network calls |
| Policy that *decides* whether to accept/promote | **NOMOS or another PDP** | EPISTEMOS enforces mechanics, **never grants** capabilities; NOMOS is **not** mandatory |
| Reputation / space-promotion decisions | **adapter / PDP** | reputation is an *input* to evaluation, never authority |

EPISTEMOS enforces: *this package is authentic, intact, correctly scoped, and fail-closed on
visibility.* It does **not** decide that the package's claims are true or that the contributor is
trustworthy — those are separate dimensions and separate subsystems.

---

## 8. Security properties & threats (summary; full model in `THREAT_MODEL.md`, EPISTEMOS-07)

- **Tamper of body** → chain verification (check 3) and content-hash (check 5) both fail.
- **Truncation / full re-chain of body** → ledger anchor (check 6) fails against `expected_head`.
- **Forged issuer** → signature (check 4) fails; issuer must match the verifying key.
- **Cross-scope injection** (the A-01 class, over the package boundary) → `_apply` scope authority
  + `_guard_payload_scope` reject it even if the chain is internally valid.
- **PRIVATE → PUBLIC leak via missing config** → `space` absence is PRIVATE, never PUBLIC (check 7).
- **Replay of revoked knowledge** → content hashes + `package_id` + applied revocation (§6.5).
- **Evidence laundering / Sybil confirmation** → out of scope for the package format itself;
  handled at claim-review/reputation layers (EPISTEMOS-05/07). The package guarantees *authenticity
  and provenance of the bytes*, not the *truth* of the claims — deliberately.

---

## 9. Open design questions (to resolve in the EPISTEMOS-06 ADR)

1. **Canonicalization for `body_sha256` and signature.** Reuse `_util.canonical_json` (already the
   ledger's canonicalization authority) so signer and verifier agree byte-for-byte. Confirm it is
   stable across schema migrations.
2. **Key distribution & rotation.** `issuer`/`key_id` format (DID vs. bare key id), trust-on-first-
   use vs. a consumer-managed keyring. Out of core; a `Verifier`-port concern.
3. **Multi-package accumulation.** `import_events` targets an *empty* engine; define the candidate-
   staging model for merging several packages under policy without violating "no silent interleave".
4. **Revocation addressing.** Revoke by `package_id`, by per-fact `entry_hash`, or by a
   subject/predicate selector — and how a consumer proves it applied the right one.
5. **Manifest ↔ body schema independence.** `manifest_version` vs. `body_schema_version` evolution
   rules (the example pins both at 1).
6. **Per-space partitioning interaction** (OV-04). If EPISTEMOS-04 partitions the FTS index per
   space, EXPORT scoping should align to the same space boundary.

---

## 10. Traceability

| This spec references | Source |
|---|---|
| Body shape, `EXPORT_FORMAT`, re-seal, `scope`, `resealed` | `src/epistemos/core/__init__.py:1348-1419`, `:1599` |
| `verify_chain(expected_count, expected_head)` | `src/epistemos/ledger/__init__.py:141-181` |
| `verify_integrity` anchor pass-through | `src/epistemos/core/__init__.py:1294-1306` |
| Fail-closed import (empty target, no-chain, schema) | `src/epistemos/core/__init__.py:1421-1477` |
| Scope authority on projection (A-01) | `src/epistemos/core/__init__.py:283-297` |
| Principal / capabilities / `export` cap | `src/epistemos/identity/__init__.py:54-66`, `:103-108` |
| `SCHEMA_VERSION = 1` | `src/epistemos/model/__init__.py:38` |
| A-11 (scoped export), A-01 (import scope), A-12 (append-only tx), B-02 (namespace≠space), B-06 (source scope) | `docs/audit/EPISTEMOS_V0_2_AUDIT.md` |
| Q8, §13/§15/§17/§25/§31 decisions; mandated output block | `docs/collaboration/COLLABORATIVE_KNOWLEDGE_MODEL.md` |

**Deferred.** This is EPISTEMOS-06 design. The export/import foundation shipped in EPISTEMOS-03;
the manifest envelope, signing/verification, and revocation application described here do **not**
ship in v0.3.
