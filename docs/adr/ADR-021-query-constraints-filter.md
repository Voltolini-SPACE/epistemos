# ADR-021 — A query constraint filters: one meaning for both retrieval paths

**Status:** Accepted (v0.3) — supersedes the retrieval-semantics half of ADR-017 §2

## Context

v0.2 shipped two retrievers behind one `Engine.search`: `IndexedRetriever` (FTS5) when the index
is `HEALTHY`, `LegacyScanRetriever` otherwise. ADR-019 guarantees the fallback never returns
"stale/incomplete" data and calls the scan "the correct O(N)" reference. ADR-017 §2 simultaneously
calls the *indexed* result set "standard search semantics" and records that the scan
"additionally surfaced non-matching objects" as an intentional difference.

Both documents cannot be the reference, and the EPISTEMOS-03 audit measured what that ambiguity
cost (findings A-03, A-04). On the frozen v0.2.0 tag, one query answered by the two paths:

| query | indexed | scan |
|---|---|---|
| `text="zzzznonexistentqqq"` (matches nothing) | 0 results | **every object in the namespace** |
| `subject="Alice", kinds=("document",)` | 0 results | **the document** |

The scan's totals stayed positive because `recency` alone is non-zero for every object, so an
unmatched query still cleared the `total > 0` bar. The consequence is worse than a ranking
difference: because `Engine.search` silently switches paths on index health, an index degradation
converted *"find what matches"* into *"list the namespace, ranked by recency"* — a strictly larger,
less precise answer to the same question. ADR-019's guarantee held literally (nothing stale) while
the user-visible meaning of the query changed.

The second row is not a fallback artifact; it is the reverse divergence, and it was undocumented.
`IndexedRetriever` applied `subject`/`predicate`/`object` as a **filter** (via `store.facts`), while
the scan applied them only as the `exact` **scoring component**, so a structural query returned
different sets on the two paths regardless of index health.

## Decision

**A supplied query constraint filters the candidate set. Both retrievers apply the same
predicate.**

1. **Text.** When the query text yields at least one token, a candidate must match at least one
   term. Objects with no lexical overlap are not results, whichever path serves the query.
2. **Structural.** When `subject`, `predicate` and/or `object` are supplied, a candidate must
   satisfy **all** of them. Only facts carry those fields, so a non-fact can never satisfy a
   structural constraint — `subject="Alice", kinds=("document",)` is legitimately empty.
3. **Unconstrained.** With no text and no structural constraint, `search` still browses the scope
   (unchanged), ranked by recency/authority/temporal.

The shared predicate is `retrieval.matches_structural`; the lexical rule lives in each retriever's
candidate loop. `exact` remains in `score_components` for explainability — it now reports *how
completely* a returned fact matched, and is no longer load-bearing for membership.

The two documented differences that **remain** (ADR-017 §1 and §3) are genuinely about scoring and
cost, not meaning: the lexical formula (BM25 vs TF·IDF) and thus fine ordering among lexical ties,
and the `CANDIDATE_POOL` recall bound on the indexed path.

## Consequences

- **The fallback is now safe in the sense ADR-019 intended.** Index health changes latency, not
  the answer. `test_degraded_index_answers_the_same_question` pins this.
- **This is a v0.1/v0.2 behaviour change**, deliberately breaking: `search(text=…)` that used to
  return recency-ranked non-matches now returns fewer (often zero) results. Callers that relied on
  search-as-browse must omit the text argument, which is what that operation actually is.
- `RETRIEVAL_SEMANTIC_PARITY` becomes an exact set equality rather than "equal after filtering the
  scan's output by `lexical > 0`", which is what the v0.2 parity test had to do — the test was
  compensating for the divergence rather than detecting it.
- No performance cost: the scan gained a cheap per-candidate predicate; the indexed path already
  filtered structurally and gained the same predicate on its text branch (where it previously
  ignored structural constraints entirely — a third divergence this closes).

## Rejected alternatives

- **Make the indexed path match the scan** (return non-matching recency hits). Rejected: it makes
  "search" mean "list everything", forfeits the index's whole point, and cannot scale — the
  candidate set becomes the entire namespace.
- **Keep both behaviours and expose a `strict=` flag.** Rejected: the flag would have to default to
  something, and either default leaves the fallback changing meaning. One engine, one answer.
- **Leave it documented as-is.** Rejected: the divergence was documented in a test docstring and
  ADR-017 §2, but its interaction with ADR-019's automatic fallback was not — and that interaction
  is the part that actually reaches a caller.
