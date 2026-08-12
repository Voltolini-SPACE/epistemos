# EPCTX/1 — EPISTEMOS Context Protocol, version 1

**Status:** Stable (EPISTEMOS v0.7.0). Normative. Frozen under ADR-038; changes follow
[VERSIONING.md](VERSIONING.md).

EPCTX/1 is a **consumption contract**. Any agent — local, over REST, or over MCP — can request
context and read it without knowing a single EPISTEMOS internal, and EPISTEMOS depends on no
consumer. EPISTEMOS provides knowledge, memory, provenance, temporal state, contradictions, and the
context envelope; the consumer decides how to reason, which model to use, and what action to attempt;
a policy engine decides what is allowed. EPISTEMOS never executes an external action, grants a
capability, or mandates a provider.

## Document

An EPCTX/1 document is a JSON object. Required top-level fields (a conforming consumer may rely on
these existing; a producer self-checks them):

```jsonc
{
  "protocol_version": "EPCTX/1",

  "request": {
    "query": "Datastore",
    "intent": "current",              // current | historical | change | decision | contradiction
    "intent_confidence": "high",      // high | low
    "temporal_scope": { "as_of": null },
    "requested_budget": null,         // optional token budget (experimental packing)
    "consumer_profile": null          // optional, advisory; never carries authority
  },

  "context": {                         // authorized objects, SECTIONED BY TYPE (§24)
    "facts":     [ <object> ],
    "claims":    [ <object> ],
    "evidence":  [ <object> ],
    "reviews":   [ <object> ],
    "decisions": [ <object> ],
    "sources":   [ <object> ]
  },

  "contradictions": [                  // SEPARATE from support (§8)
    { "id", "object_type", "text", "relation", "provenance" }
  ],
  "disputed": true,                    // convenience: contradictions is non-empty

  "temporal": {                        // temporal contract (§9)
    "as_of": null,
    "has_current_state": true,
    "has_historical_state": false
  },

  "completeness": {                    // honest omission (§7)
    "complete": false,
    "reasons": [ "history_collapsed" ]
  },

  "provenance": {                      // queryable "why is this here?" (§10)
    "items": [ { "id", "object_type", "source", "derived_from", "evidence_refs" } ],
    "refs":  [ "source:...", "evidence:..." ]
  },

  "token_estimate": 26,                // estimate (§11)
  "tokens_by_section": { "facts": 6, "claims": 0, "evidence": 0, "contradictions": 0, ... },
  "tokenizer_profile": "chars-per-token-4/estimate-1",

  "expansion": {                       // EXPERIMENTAL (§21)
    "available": true,
    "handles": [ { "handle", "group_kind", "collapsed_count", "tokens_saved" } ]
  },

  "integrity": {                       // content digest (§6)
    "algo": "sha256/canonical-json-1",
    "context_hash": "sha256/canonical-json-1:<hex>"
  },

  "metadata": {}
}
```

### Object shape (every element of a `context.*` array)

```jsonc
{
  "id": "fact_...",
  "object_type": "fact",              // fact | claim | evidence | review | decision | source
  "text": "Datastore is postgres",
  "role": "current",                  // contradiction | current | decision | support | history
  "belief_state": "asserted",         // fact: "asserted"; claim: proposed|supported|disputed|accepted
  "accepted_state": null,             // claim: bool (governed acceptance); else null
  "relation": null,                   // evidence: contradicts|weakens|supports; else null
  "temporal": { "valid_from", "valid_to", "transaction_from", "transaction_to", "is_current" },
  "provenance": { "source", "derived_from": [...], "evidence_refs": [...] },
  "tokens": 6
}
```

## Normative rules

1. **Types are explicit.** Every object carries `object_type`. A claim carries `belief_state` and
   `accepted_state`; a bare or disputed claim has `accepted_state = false`. A consumer must never
   treat a `claim` as a `fact` — the document makes the distinction machine-checkable (§23, §24).
2. **Contradictions are a section.** Disputing evidence appears in `contradictions`, not mixed into
   `context.evidence`. `disputed` is a boolean the consumer can branch on (§8).
3. **Completeness is declared.** `completeness.complete` plus `reasons` from a fixed vocabulary
   (`history_collapsed`, `token_limit`, `continuation_available`, `evidence_unavailable`,
   `authorization_limited`). Silence is never "nothing to know" (§7).
4. **Temporal is a contract.** Each object exposes valid and transaction time and `is_current`; the
   document declares whether it carries current and/or historical state. A consumer distinguishes
   "believed now" from "believed then" without parsing timestamps (§9).
5. **Provenance is queryable.** Per-object `source` / `derived_from` / `evidence_refs` answer "why is
   this here?" with no internals (§10).
6. **Tokens are an estimate.** `token_estimate` and `tokens_by_section` are estimates; the
   `tokenizer_profile` is recorded. No claim of cross-tokenizer precision (§11).
7. **Integrity travels with it.** `integrity.context_hash` is SHA-256 over the canonical JSON of the
   document with its own `integrity` block removed. Any alteration changes the hash (§6).
8. **Identity is server-side.** The producer derives tenant / principal / capabilities from the
   caller's binding (local Principal, REST token, MCP server principal). The request body, tool
   args, `query`, and `consumer_profile` never carry authority (§17, §19, §28).

See: [SERIALIZATION](SERIALIZATION.md), [VERSIONING](VERSIONING.md), [COMPLETENESS](COMPLETENESS.md),
[TEMPORAL](TEMPORAL.md), [PROVENANCE](PROVENANCE.md), [TOKEN_ACCOUNTING](TOKEN_ACCOUNTING.md),
[SECURITY](SECURITY.md), [RENDERING](RENDERING.md), [CONSUMER_GUIDE](CONSUMER_GUIDE.md).
