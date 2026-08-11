# ADR-004 — Provenance model: PROV-aligned genealogy over the ledger

**Status:** Accepted (v0.1)

## Context
Every relevant fact must answer WHERE DID THIS COME FROM, and every decision WHAT EVIDENCE LED TO
THIS. The census showed provenance ranging from none (Mem0/Letta) to standardized (TrustGraph
PROV-O), but **no surveyed system content-hashes its provenance** into tamper-evidence.

## Decision
A lightweight mapping onto **W3C PROV** three roles:
- **Entity (PROV)** = an EPISTEMOS object (fact/source/document/decision);
- **Activity (PROV)** = a ledger event (`fact_asserted`, `document_ingested`, …);
- **Agent (PROV)** = the `actor`/`principal` recorded on each ledger event.

`explain(obj_id)` walks derivation edges (`source`, `derived_from`, `supersedes`, `contradicts`) and
cross-references the ledger for the activities that touched the object, so genealogy is **auditable,
not asserted**. Observations/documents store a `source_hash` binding their content. `explain` is
cycle-safe and depth-bounded. Confidence and source trust are recorded as **separate** fields
(confidence ≠ truth). PROV-O/PROV-JSON is an **export** target, not the storage model (ADR-014).

## Consequences
- Multi-hop genealogy (source→observation→fact A→fact B→decision) is tested.
- Content hashing + the hash chain make provenance tamper-evident — a census-wide gap we close.
- `explain` scans the ledger for activities (O(events)); made cheap via short-circuit ref checks;
  a provenance index is a v0.2 optimization if measured need arises.

## Rejected alternatives
- **Classic RDF reification / pre-1.2 RDF-star** for statement metadata: verbose / unstable
  (RDF 1.2 still CR). Rejected for storage; PROV export used for interop.
- **Provenance-by-compliance-narrative** (ABI): not enforced lineage. Rejected.
