# Redundancy Collapse — what may fold, what never may

The envelope collapses only **safe** redundancy, and only enough to shorten the transmission. Token
economy never beats recall (§8).

## COLLAPSIBLE (safe)

| class | rule | on collapse |
|---|---|---|
| **Superseded current-state versions** | multiple versions of one statement (`kind:subject\|predicate`) where the current one supersedes the priors — **only** when intent is confidently `current` | keep the current inline; fold priors into a `collapsed_history` group; set `context_incomplete` + `history_collapsed` |
| **True duplicates** | identical content (**same `content_hash`**) | keep one representative inline; fold the rest into a `duplicate` group; **no** incompleteness (nothing lost) |

## NEVER collapse

- **Contradictions** — pinned, always delivered (including one attached to a retrieved claim).
- **Independent corroboration** — same finding from *different sources*. `corroboration ≠ duplicate`
  (§24): distinct `content_hash` (or no hash) ⇒ every source is retained. Only identical content
  may fold. Keying redundancy by *title* would wrongly collapse corroboration — the code keys on
  `content_hash` alone, and a mutation to title-keying is caught by the test suite.
- **Historically-relevant versions** — any `historical` / `change` / `decision` / `contradiction`
  intent, or an *uncertain* intent, preserves the full version history inline.
- **Decisions, reviews, evidence with unique provenance** — never folded.

## Intent gate (§8)

`_may_collapse_history(intent, confidence)` returns true **only** for `("current", "high")`.
`classify_intent` assigns `high` confidence only when the query carries a single clear signal;
anything ambiguous is `("current", "low")`, which forbids collapse. When unsure, the envelope keeps
everything.

## Provenance preservation (§10)

Every collapse keeps the genealogy: the representative (`current`), the folded ids (`collapsed`),
their `sources`, and a re-expansion `handle`. `reachable_ids()` always includes every folded id —
collapsing is a *view*, not a deletion.

## Why this is the only surviving win

EPISTEMOS-06 falsified Dimensions / Resonance / Microconnections / Contextual Geometry — they did
not beat the baseline and were rejected. EPISTEMOS-07 isolated the one mechanism that did: preserve
the evidence, collapse only provably-safe redundancy, and be honest about it. EPISTEMOS-08 re-proved
that mechanism at scale (1000+ state changes) before promoting it. See
[BENCHMARK.md](BENCHMARK.md).
