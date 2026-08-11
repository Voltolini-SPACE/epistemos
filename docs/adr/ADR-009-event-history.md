# ADR-009 — Event history: hash-chained, tamper-evident (not "immutable")

**Status:** Accepted (v0.1)

## Context
We need to detect adulteration of history without building a "blockchain for aesthetics" (mission
§18). No surveyed competitor content-hashes its history.

## Decision
The ledger is **append-only and hash-chained**: each record commits to `content_hash` (sha256 of the
canonical payload) and `prev_hash` (previous record's `entry_hash`), forming a tamper-evident chain.
`verify_chain` detects payload edits, header edits, mid-chain removals/reorders (seq gaps),
duplicates, `prev_hash` swaps, and forged inserts that were not fully re-chained. We call this
**TAMPER-EVIDENT, not immutable**: a bare hash chain cannot detect **tail-truncation** or a **fully
re-chained rewrite** without an external anchor, so `verify_chain`/`verify_integrity` accept
`expected_count`/`expected_head` to catch those. Payloads are snapshotted through canonical JSON at
seal time so later projection mutations can never alter a sealed record.

## Consequences
- Any logical tampering of history is detected (tested for all nine attacks in §18 + anchors).
- The honest crypto framing avoids over-claiming; the anchor must be stored out-of-band.
- No consensus/PoW/p2p — only the primitives that buy tamper-evidence for a local single-writer log.

## Rejected alternatives
- **Calling it "immutable"**: false without external anchoring or WORM storage; rejected.
- **Merkle tree per event**: unnecessary for a single-writer linear log; a hash chain suffices.
- **A real blockchain**: gratuitous infra; rejected (mission §18).
