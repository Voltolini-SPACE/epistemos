# ADR-039 — EPCTX canonical serialization and integrity

**Status:** Accepted (v0.7.0)

## Context

For `context_hash` to be meaningful and for two runtimes to agree on a document, one logical context
must serialize to exactly one byte string. And a consumer needs a cheap way to detect alteration in
transit or storage.

## Decision

- **Canonical JSON**: UTF-8, sorted keys, compact separators, `ensure_ascii=False`, `allow_nan=False`.
  No pickle, no arbitrary-object or runtime-specific binary format (§5).
- **Integrity**: `context_hash` = `sha256/canonical-json-1:<hex>` over the canonical JSON of the
  document with its own `integrity` block removed, so the hash never depends on itself (§6).
- `SAME_LOGICAL_CONTEXT → SAME_CANONICAL_SERIALIZATION`, modulo intentionally-variable fields (ids,
  timestamps, freshly-minted handles).

## Consequences

- Documents are diffable and hashable; tampering is detectable (`test_integrity_detects_tampering`).
- No cryptography is invented; signing (if ever) is a separate port over the same canonical form.

## Alternatives rejected

- **Default `json.dumps`** — key order and whitespace vary; hashes would not agree.
- **Pickle / msgpack of objects** — unsafe, runtime-specific, opaque to non-Python consumers.
