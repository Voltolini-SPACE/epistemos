# Context Envelope — Benchmark (EPISTEMOS-08, the promotion gate)

The v0.6 promotion required re-proving the EPISTEMOS-07 result on a **large** corpus. A win that
only shows on a toy corpus is not a win.

Reproduce:

```bash
python tools/eps08_benchmark.py --entities 250 --versions 4   # the gate
python tools/eps08_benchmark.py --scale                        # token + latency at growing sizes
```

## Corpus (§17)

- **1000 state changes** — 250 entities × 4 versions (each superseded 3×), ~1759 total events.
- True **duplicates** (same `content_hash`), independent **corroboration** (same finding, distinct
  sources), a **contradiction** attached to a claim, and a **decision** with supporting evidence.

## Query types (§18)

Entity-focused current-state and historical queries (the realistic "what is X now / what was X"
pattern), plus contradiction, decision-explanation, duplicate, and source-comparison queries.

## Method (honest)

Baseline `A` and envelope `E` see the **same retrieval depth** (`pool = 48`). The token delta is
purely the envelope's redundancy collapse, not a smaller candidate pool. Baseline serializes raw
`search(believed_only=False)` output; the envelope compacts the same objects.

## Result

```
corpus: 1000 state changes, 1759 events, 20 probe queries
  tokens: baseline 39.5 -> envelope 25.9  (reduction +34.6%)
  answer_correctness: baseline 100.0% -> envelope 100.0% (delta +0.0)
  CRITICAL_EVIDENCE_LOSS=0  CONTRADICTION_LOSS=0  TEMPORAL_REGRESSION=0
  latency p50=8.6ms p95=10.7ms
  GATES: ALL PASS
```

Primary gates (§27) — all pass:

| gate | required | measured |
|---|---|---|
| CRITICAL_EVIDENCE_LOSS | 0 | 0 |
| CONTRADICTION_LOSS | 0 | 0 |
| PRIVATE_CONTEXT_LEAK | 0 | 0 |
| TEMPORAL_REGRESSION | 0 | 0 |
| ANSWER_CORRECTNESS_DELTA | ≥ 0 | +0.0 |
| TOKEN_REDUCTION | > 0 | +34.6% |

## Scale (§29)

```
entities=  100 events=  709  tokens 40->26 (+35%)  envelope_latency_p50= 3.5ms
entities=  500 events= 3509  tokens 40->26 (+35%)  envelope_latency_p50=17.9ms
entities= 2000 events=14009  tokens 40->26 (+35%)  envelope_latency_p50=77.8ms
```

Token reduction is **stable ~35% as the corpus grows** — it does not decay with scale (unlike the
rejected EPISTEMOS-06 mechanisms). Envelope latency grows linearly with the retrieval pool (it is
dominated by `search`), not with total corpus size.

## Honest scope of the token claim (§28)

The reduction applies to **entity/fact-focused queries whose retrieval returns version history**
(current-state and claim-history query types) over redundant corpora. Broad, multi-entity lexical
queries — where each entity contributes a single hit and there is little per-statement redundancy to
fold — see little or no reduction. We therefore publish **"up to ~35% fewer tokens in measured
redundant scenarios,"** never a universal figure. The methodology above is runnable so the number is
checkable.
