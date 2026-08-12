# Contradiction Pinning

A contradiction is the single most expensive thing to lose from a context: it flips an answer. The
envelope **pins** contradictions so they are always delivered inline, never folded, never dropped —
not even by the experimental token budget.

## What gets pinned

1. **Retrieved contradictions** — any object in the authorized retrieval that is a contradiction
   (`kind == evidence` with `metadata.relation ∈ {contradicts, weakens}`).
2. **Attached contradictions** — a contradiction attached to a *retrieved claim* via that claim's
   `metadata.evidence_links` (relation `contradicts`/`weakens`), even if the contradiction itself
   was not a top retrieval hit.

Case 2 is the *only* place the envelope follows a relation beyond the raw retrieval — and it is the
sharpest security edge (see below).

## Authorization (the security edge)

Following an attached contradiction must never leak a **private** contradiction attached to a
**shared** claim. So each attached contradiction is re-authorized:

```python
ev = self._eng.store.get_object(link_id)
if ev is not None and self._eng.is_readable(principal, ev):   # re-authorized, per principal
    pin(ev)
```

The claim may be readable by Bob while the contradiction Alice attached to it is private to Alice.
Bob's envelope must not reveal it. `is_readable` is checked for *this* principal on *every* attached
contradiction. Removing that check is a mutation the test suite kills
(`test_private_contradiction_attached_to_shared_claim_no_leak`, mutation M3).

## Guarantees

- A pinned contradiction is always in `items` and listed in `pinned_contradictions`.
- It survives redundancy collapse and experimental budget packing unconditionally.
- If a contradiction the baseline could reach is *not* delivered (e.g. filtered by authorization),
  the envelope declares `context_incomplete` rather than silently hiding it.
- `CONTRADICTION_LOSS = 0` is a primary benchmark gate (§27) and is 0 at 1000+ state changes.
