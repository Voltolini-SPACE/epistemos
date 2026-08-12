# EPCTX/1 — Token accounting

The document exposes what it costs, honestly (§11).

```jsonc
"token_estimate": 26,
"tokens_by_section": { "facts": 6, "claims": 0, "evidence": 0, "contradictions": 0,
                       "reviews": 0, "decisions": 0, "sources": 0 },
"tokenizer_profile": "chars-per-token-4/estimate-1"
```

- The field is named **`token_estimate`**, never `tokens` — it is an estimate, not a promise. The
  `tokenizer_profile` records how it was produced (default: ~4 characters per token).
- `tokens_by_section` breaks the estimate down so a consumer can see where the budget goes and decide
  what to trim or expand.
- We do **not** pretend precision across different providers' tokenizers. A consumer that needs
  exact counts for a specific model should re-count with that model's tokenizer; the estimate is for
  budgeting and comparison.

**Budgeting.** A consumer may pass `requested_budget` (or `consumer_profile.max_context_tokens`) to
ask the producer to fit the document to a token budget. This engages the experimental packer
(ADR-037), which never drops a pinned contradiction or a critical item and declares any drop in
`completeness` (`token_limit`). The protocol never *inflates* tokens: the structured document plus a
compact render stays smaller than raw retrieval in measured redundant scenarios
(see [BENCHMARK in the agent bench](../../tools/eps09_agent_bench.py)).
