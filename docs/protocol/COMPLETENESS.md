# EPCTX/1 — Completeness

A consumer must never read silence as "nothing to know" (§7). Every document declares:

```jsonc
"completeness": { "complete": false, "reasons": ["history_collapsed"] }
```

Reason vocabulary:

| reason | meaning |
|---|---|
| `history_collapsed` | superseded versions were folded (reachable via an expansion handle) |
| `token_limit` | experimental budget packing dropped items |
| `continuation_available` | an experimental continuation handle is offered for dropped items |
| `evidence_unavailable` | referenced evidence could not be materialized |
| `authorization_limited` | a related object exists but is not readable by this principal |

Rules:

- A true-duplicate collapse loses nothing (bit-identical, both ids reachable) and does **not** set
  incompleteness.
- A history collapse omits versions from the inline view (though reachable) and **does** set
  `complete: false` with `history_collapsed`.
- A pinned contradiction filtered by authorization sets `authorization_limited` rather than being
  hidden silently.

A consumer that ignores `completeness` is making an auditable mistake: the signal is explicit in the
data. See the bad-consumer tests in `tests/protocol/test_renderer_harness.py`.
