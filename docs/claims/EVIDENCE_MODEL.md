# Evidence model

**Evidence** is a typed artifact that relates to claims. EPISTEMOS records evidence as a
**reference**, not necessarily a copy: a URI plus a content hash is a valid, integrity-checkable
citation (§5) — the engine never needs to hold (or egress to fetch) the bytes.

## Shape

`claims.Evidence` (`kind="evidence"`) subclasses `Envelope`, plus:

| field | meaning |
|-------|---------|
| `evidence_kind` | `document` / `uri` / `hash` / `observation` / `dataset` / `artifact` / `event` / `external_record` |
| `title`, `uri` | human label + locator (locator is a reference, not fetched) |
| `content_hash` | integrity anchor for the referenced content |
| `origin` | where the *evidence* came from (may differ from the claim's source) |
| `captured_at` | when the evidence was captured |

Evidence is a first-class, space-scoped object with its own owner and visibility. It is created with
`create_evidence(...)` (`evidence.create`, a default right) and is PRIVATE by default.

## Typed attachment — *attached is not supports* (§6)

Evidence links to a claim through a **typed relation**, recorded by `EVIDENCE_ATTACHED`:

`supports` · `contradicts` · `weakens` · `derived_from`

`attach_evidence(evidence_id, to_claim, relation)` requires `evidence.attach` **and read access to
both** the claim and the evidence — you cannot attach something you cannot see, and the relation is
preserved verbatim (contradicting evidence is never silently upgraded to supporting). The link is
stored on the claim's projection and read back through `claim_evidence`, which **filters by evidence
readability** (see `VISIBILITY_COMPOSITION.md`): a claim that is broadly visible never exposes
evidence the viewer is not allowed to read.

## Why references, not copies

Local-first and zero-egress: the engine cites external material by hash without pulling or
redistributing it. Integrity is checkable (the hash pins the content) while sovereignty and privacy
are preserved. See `ADR-028`.
