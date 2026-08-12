# Claim graph API

All methods hang off `Engine` and take a `Principal` first. Every mutation is a ledger event;
every read applies the space firewall before returning. PRIVATE by default; a `space` argument
places an object. Capabilities in **bold** are *non-default* (must be granted).

## Contribution

```python
claim = engine.create_claim(
    principal, subject="CompanyX", predicate="acquired", object="CompanyY",
    claimant="analyst_jo",           # defaults to principal.agent; may be a distinct identity
    contributor_kind="human",        # human | agent | service | organization
    source=src_id,                   # external origin (must be readable if given)
    space=team_id,                   # optional; omit ⟶ PRIVATE to owner
)                                    # cap: claim.create

engine.retract_claim(principal, claim.id, reason="mistake")          # cap: claim.retract

ev = engine.create_evidence(
    principal, evidence_kind="document", title="CVM filing",
    uri="https://…", content_hash="…", origin="CVM", space=team_id,
)                                    # cap: evidence.create

engine.attach_evidence(
    principal, evidence_id=ev.id, to_claim=claim.id,
    relation="supports",             # supports | contradicts | weakens | derived_from
)                                    # cap: evidence.attach  (+ read of BOTH sides)
```

## Review

```python
engine.review_claim(
    principal, claim.id, verdict="confirm",   # confirm|dispute|reject|request_evidence|abstain
    rationale="matches the filing", evidence_refs=[ev.id],
)   # cap: claim.confirm / claim.dispute / claim.review  (+ read of the claim)
```

## Governance (the truth gate)

```python
engine.accept_claim(principal, claim.id, reason="verified")   # cap: **knowledge.accept**
engine.reject_claim(principal, claim.id, reason="unsupported") # cap: **knowledge.accept**
```

Denied if the principal is the claim's `claimant` (no self-acceptance, §32). The engine enforces the
capability *before* the injected `Policy` runs. Wire a custom policy with
`Engine(store, policy=my_policy)`; the default `LocalDefaultPolicy` is deterministic and offline.

## Reads

```python
engine.belief(principal, claim.id)
# -> {"state": "disputed", "why": "...", "reviews": [...], "governance": None}

engine.claim_evidence(principal, claim.id)
# -> [{"evidence": id, "relation": "supports", "evidence_kind": ..., "uri": ..., "title": ...}]
#    filtered to evidence the caller may read (§15)

engine.explain_claim(principal, claim.id)
# -> {statement, claimant, contributor_kind, ingested_by, source, evidence, reviews,
#     contradictions, belief, space, temporal}   (authorization applied BEFORE traversal)

engine.search(principal, text="acquired", kinds=("claim",))   # claims are searchable
```

## Errors (fail-closed)

- `NotFoundError` — the object is absent **or** outside your spaces (indistinguishable: no oracle).
- `AuthorizationError` — missing capability, or self-acceptance, or policy denial.
- `ConflictError` — retract/supersede of an already-closed claim (append-only, first-close-wins).
- `ValidationError` — wrong object kind, unknown verdict/relation/kind, malformed field.

See `CLAIM_MODEL.md`, `EVIDENCE_MODEL.md`, `REVIEW_MODEL.md`, `BELIEF_MODEL.md`,
`VISIBILITY_COMPOSITION.md`, `ADR-028`, `ADR-029`.
