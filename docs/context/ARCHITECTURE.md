# Context Envelope — Architecture

> Compress the *transmission* of memory, never the memory.

EPISTEMOS keeps the whole sovereign, bitemporal, auditable knowledge base. An agent rarely needs
all of it for a single inference — but it does need the *right* pieces, with their contradictions
and provenance intact. The **Context Envelope** is a post-retrieval transform that turns the objects
the current retrieval already returned into an evidence-preserving, compact context.

It never widens the candidate set, never invents a new retrieval path, and never lowers an
authorization boundary. It is additive: `engine.search` is unchanged and remains the way to get raw
results.

## Pipeline

```
query
  → authorization        (Principal; capability firewall)
  → current retrieval     (engine.search, believed_only=False — history included)
  → authorized objects    (is_readable re-checked; skip kinds)
  → contradiction pinning (retrieved OR attached-to-a-retrieved-claim, each re-authorized)
  → redundancy analysis   (intent-aware: only a confident CURRENT intent may collapse history)
  → safe collapse         (superseded current-state versions; true duplicates by content_hash)
  → Context Envelope      (EPCTX/1; provenance kept; context_incomplete declared honestly)
  → agent
```

## What it is / is not

| It is | It is not |
|---|---|
| A post-retrieval transform over authorized objects | A new retriever or an index |
| Evidence- and provenance-preserving | Lossy summarization |
| Intent-aware (conservative when unsure) | An aggressive token minimizer |
| Honest about omission (`context_incomplete`) | A silent truncator |

## Boundaries (invariants)

1. **No widening.** The envelope only ever sees what `search` returned. The single relation it
   follows — a claim's *attached* contradiction — is re-authorized against `Engine.is_readable`
   before it is pinned. Nothing else is dereferenced.
2. **Authorization is server-side and re-checked.** Every candidate and every attached contradiction
   passes `is_readable` inside the builder (defense-in-depth; `search` already firewalled).
3. **Collapsing ≠ losing.** Every folded object id and its provenance stay *reachable* behind a
   `RedundancyGroup` handle. Nothing is deleted; the transmission is shorter, the memory is whole.
4. **Honesty.** Any real omission (history collapsed, a pin missing from the inline set, a
   token-budget drop) sets `context_incomplete` with a machine-readable reason.

## Components

- `estimate_tokens(text)` — deterministic ~4-chars-per-token estimate (declared an *estimate*).
- `classify_intent(query) -> (intent, confidence)` — conservative; `high` only on a single clear
  signal. Ambiguous or unmarked queries are `("current", "low")`, which forbids collapse.
- `ContextEnvelopeBuilder(engine).build(principal, query, *, config, at_tx, intent)` — the transform.
- `ContextEnvelope` — the `EPCTX/1` value object (`to_dict()` for the wire).
- `EnvelopeConfig` — stable knobs (`pin_contradictions`, `collapse_redundancy`, `top_n`) and
  **experimental, off-by-default** knobs (`budget_pack`, `token_budget`, `continuation`).

## API surface

`engine.context(principal, query, *, compact=True, at_tx=None, intent=None) -> dict` returns the
`EPCTX/1` envelope; `compact=False` returns raw search results. See [API.md](API.md).

## Stability

Stable in v0.6: contradiction pinning, intent-aware safe redundancy collapse, honest
`context_incomplete`. Experimental (opt-in): token-budget packing and continuation handles — proven
useful in EPISTEMOS-07 research but held out of the default path until independently hardened.

See ADR-033…037.
