# Retrieval receipts

The event ledger proves what the system **wrote**. It proves nothing about what an agent was
**shown**, and that is the question that gets asked when a decision is challenged: *which context
did it actually have?* Re-running the query does not answer it, because the projection has moved
on since.

A `RetrievalReceipt` seals one retrieval so that question stays answerable.

```python
results, receipt = engine.search_sealed(ctx, text="retention window")

receipt.verify()                      # tamper-evident
receipt.matches_query("retention window")   # constant-time, without storing the query text
receipt.projection_version            # which state it ran against
receipt.weights                       # how it was ranked
receipt.results[0]["score_components"]  # why that result was first
```

## What it proves

| question | field |
|---|---|
| which query? | `query_hash` (the text itself is never stored) |
| against which state? | `projection_version` — the ledger length the projection was built from |
| which algorithm? | `scorer_version` |
| with which weights? | `weights` — read from the declared dataclass fields, so a new weight cannot be silently omitted |
| what was returned, in what order? | `results[].rank`, `results[].id` |
| why was each result ranked there? | `results[].score`, `results[].score_components`, `results[].why_returned` |
| was it altered afterwards? | `receipt_hash` |
| were receipts *removed*? | `previous_receipt_hash` + `ReceiptChain` |

## Determinism

The digest covers a canonical payload that **excludes wall-clock time**. Timestamps and timings
live in `execution`, deliberately outside the hash — otherwise two identical retrievals would seal
differently and nothing could ever be replayed. The same query against the same projection
produces the same `receipt_hash`, asserted by test.

## What it is not

A receipt is **not** an authority. It records that these candidates were returned in this order.
Whether any of them is true remains a matter for evidence, review and governance. Sealing a
retrieval must never be mistaken for accepting its contents — `retrieval ≠ acceptance` is the
same rule that makes compiled claims `PROPOSED` rather than facts.

Signing is optional: pass `secret=` to add an HMAC and make the receipt *attributable*. Without a
key it is still tamper-evident, just not attributable to a holder.

No new dependency: `hashlib` and `hmac` are standard library.
