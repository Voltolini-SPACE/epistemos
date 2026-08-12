# Context Envelope — Schema `EPCTX/1`

The value returned by `engine.context(...)` and by `ContextEnvelope.to_dict()`.

```jsonc
{
  "format": "EPCTX/1",
  "query": "Datastore",
  "intent": "current",             // current | historical | change | decision | contradiction
  "intent_confidence": "high",     // high | low  (low ⇒ collapse suppressed)
  "at_tx": null,                   // as-of transaction time, or null for now

  "items": [                        // the delivered inline context, role-ordered
    {
      "object": "obj_...",          // object id
      "kind": "fact",               // fact | claim | evidence | decision | review | ...
      "role": "current",            // contradiction | current | decision | support | history
      "text": "Datastore is postgres",
      "tokens": 6,
      "provenance": ["obj_...", "..."]   // source/lineage ids for this item
    }
  ],

  "pinned_contradictions": ["obj_..."],  // ids pinned into items (never dropped)

  "collapsed_groups": [             // safe redundancy folded away but kept reachable
    {
      "kind": "collapsed_history",  // collapsed_history | duplicate
      "current": "obj_current",     // the representative delivered inline
      "collapsed": ["obj_prev1", "obj_prev0"],  // folded ids (still reachable)
      "handle": "grp_...",          // stable handle to re-expand
      "sources": ["obj_..."],       // provenance of folded members
      "tokens_saved": 42
    }
  ],

  "provenance_refs": ["obj_..."],   // union of all provenance referenced

  "temporal_summary": {             // what the collapse did, in the open
    "collapsed_versions": 3,
    "duplicates_folded": 1
  },

  "context_incomplete": true,       // honest omission flag
  "incomplete_reasons": ["history_collapsed"],  // machine-readable reasons (sorted, deduped)

  "token_estimate": 26,             // estimate_tokens over delivered items
  "metadata": { }                   // reserved
}
```

## `incomplete_reasons` vocabulary (§11)

| reason | meaning |
|---|---|
| `history_collapsed` | superseded versions were folded (recoverable via handle) |
| `token_limit` | experimental budget packing dropped items |
| `continuation_available` | experimental continuation handle offered for dropped items |
| `evidence_unavailable` | referenced evidence could not be materialized |
| `authorization_limited` | a related object exists but is not readable by this principal |

A **true-duplicate** collapse does *not* set `context_incomplete`: the content is bit-identical and
both ids remain reachable, so nothing is lost. Only a real omission flags incompleteness.

## Reachability

`ContextEnvelope.reachable_ids()` = delivered item ids ∪ every `collapsed_groups[*].collapsed` ∪ each
group's `current`. A consumer can always recover a folded object by its id or its group `handle`.
`object_ids()` returns only the inline (delivered) ids.

## Stability

`EPCTX/1` is frozen for v0.6 (ADR-033). Additive fields may appear under the same version; a
breaking change bumps to `EPCTX/2` with a new ADR.
