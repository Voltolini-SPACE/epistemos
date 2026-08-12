# EPCTX/1 — Provenance contract

A consumer must be able to ask **"why is this here?"** without knowing EPISTEMOS internals (§10).

**Per object** (`context.*[].provenance`):

```jsonc
{ "source": "src_...", "derived_from": ["evd_..."], "evidence_refs": ["evd_..."] }
```

- `source` — the originating source id, if any.
- `derived_from` — genealogy: the objects this one was derived from (PROV-aligned).
- `evidence_refs` — for a decision or claim, the evidence attached to it.

**Per document** (`provenance`):

```jsonc
{
  "items": [ { "id", "object_type", "source", "derived_from", "evidence_refs" } ],
  "refs":  [ "source:...", "evidence:..." ]
}
```

`items` is a flat, queryable table over every delivered object; `refs` is the union of provenance
references. A consumer can trace a decision to its supporting evidence, or a fact to its source,
using only these fields. The full genealogy remains available through `engine.explain(id)` for a
consumer that wants to go deeper — but the document alone answers the common "why" without a second
call.
