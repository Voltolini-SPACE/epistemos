# ADR-034 — Intent-aware, safe redundancy collapse

**Status:** Accepted (v0.6.0)

## Context

The token win comes from folding redundancy — but "redundant" is intent-dependent. The superseded
versions of a fact are noise to "what is X *now*?" and are the *answer* to "how did X change?".
Folding them unconditionally would corrupt historical and change queries. And two sources reporting
the same finding are corroboration, not a duplicate — folding them would erase provenance.

## Decision

Collapse **only** provably-safe redundancy, gated by intent confidence.

1. **Superseded current-state versions** fold into a `collapsed_history` group **only** when intent
   is confidently `current`. `_may_collapse_history` returns true only for `("current", "high")`.
   `classify_intent` assigns `high` only on a single clear signal; ambiguous/unmarked queries are
   `("current", "low")` → no collapse. When unsure, keep everything (§8: economy never beats recall).
2. **True duplicates** (identical `content_hash`) fold into a `duplicate` group regardless of intent
   — the content is bit-identical, so nothing is lost.
3. **Corroboration is never folded.** Redundancy is keyed on `content_hash` alone; distinct content
   (or absent hash) keeps every source. Keying on title/uri is explicitly wrong and is caught by a
   mutation test.

Every collapse preserves genealogy (representative `current`, folded `collapsed` ids, `sources`, a
re-expansion `handle`); `reachable_ids()` always includes folded ids. Collapsing is a view, never a
deletion.

## Consequences

- `historical` / `change` / `decision` / `contradiction` / low-confidence intents preserve full
  history inline; only confident current-state queries compact it.
- A true-duplicate collapse does **not** set `context_incomplete` (nothing lost); a history collapse
  does (recoverable via handle).
- Mutation gate: misclassifying history (always-collapse) and confusing duplicate/corroboration are
  both killed → `NON_EQUIVALENT_SURVIVED = 0`.

## Alternatives rejected

- **Always collapse to current** — corrupts historical/change queries (temporal regression).
- **Collapse by title/subject** — folds independent corroboration; loses provenance.
