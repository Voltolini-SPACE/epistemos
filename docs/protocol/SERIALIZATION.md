# EPCTX/1 — Serialization

**Canonical JSON.** One logical context serializes to one byte string so `context_hash` is meaningful
and two runtimes agree.

- UTF-8, **sorted keys**, compact separators (`,` and `:`), `ensure_ascii=False`, `allow_nan=False`.
- No `pickle`, no arbitrary object serialization, no runtime-specific binary format (§5).

```python
from epistemos.protocol import canonical_json
canonical_json({"b": 1, "a": [3, 2, 1]})  # '{"a":[3,2,1],"b":1}'
```

**Determinism gate.** For the same logical value — modulo intentionally-variable fields (object ids,
timestamps, freshly-minted expansion handles) — `canonical_json` returns identical bytes.
`SAME_LOGICAL_CONTEXT → SAME_CANONICAL_SERIALIZATION` (§5).

**Integrity.** `context_hash(document)` = `sha256/canonical-json-1:<hex>` over the canonical JSON of
the document with its own `integrity` block removed, so the hash never depends on itself. It detects
alteration in transit or storage; it is a content digest, **not** cryptography (§6). External signing,
if ever added, is a separate port over this same canonical form.
