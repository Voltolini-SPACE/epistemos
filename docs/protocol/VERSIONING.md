# EPCTX/1 — Versioning

`protocol_version = "EPCTX/1"`. Compatibility is by **major**.

| rule | meaning |
|---|---|
| **required fields** | The set in [EPCTX_1_SPEC](EPCTX_1_SPEC.md#document); a consumer may rely on them. |
| **optional fields** | Anything else. A consumer that does not understand an optional field **must ignore it**, not fail. |
| **unknown fields** | Tolerated. Forward compatibility: an `EPCTX/1.x` producer may add optional fields and older `EPCTX/1` consumers keep working. |
| **deprecated fields** | Kept present within the same major; documented as deprecated; removed only at the next major. |
| **breaking change** | Removing or repurposing a required field. Allowed only in `EPCTX/2`, with its own ADR. |

```python
from epistemos.protocol import is_compatible
is_compatible("EPCTX/1")     # True
is_compatible("EPCTX/1.4")   # True  (newer minor, optional additions)
is_compatible("EPCTX/2")     # False (different major)
```

A conservative consumer validates the required set and ignores the rest:

```python
from epistemos.protocol.versioning import assert_required
assert_required(doc)   # raises if a required field is missing; unknown extras are fine
```

The `versioning` module is the single authority on the version string, the required-field set, and
the compatibility function (§4).
