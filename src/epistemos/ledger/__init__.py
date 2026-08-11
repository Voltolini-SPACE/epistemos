"""Append-only, hash-chained event ledger (mission §18).

The event log is the source of truth; all queryable state is a projection of it.
Each record commits to the previous record's hash, forming a tamper-evident chain
(a hash chain — a degenerate Merkle list). Any edit to a historical payload changes
its ``content_hash``, which changes its ``entry_hash``, which breaks every subsequent
``prev_hash`` link. :func:`verify_chain` detects this.

We deliberately do **not** build a "blockchain" (mission §18): no consensus, no PoW,
no p2p. Only the primitives that buy tamper-evidence for a local, single-writer ledger.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .._util import canonical_json, hash_obj, sha256_hex
from ..errors import IntegrityError

__all__ = [
    "GENESIS_HASH",
    "Op",
    "Event",
    "LedgerRecord",
    "content_hash",
    "seal",
    "verify_chain",
]

GENESIS_HASH = "0" * 64


class Op:
    """Canonical operation names recorded in the ledger."""

    SOURCE_ADDED = "source_added"
    OBSERVATION_RECORDED = "observation_recorded"
    DOCUMENT_INGESTED = "document_ingested"
    FACT_ASSERTED = "fact_asserted"
    FACT_SUPERSEDED = "fact_superseded"
    FACT_RETRACTED = "fact_retracted"
    FACT_CONFIRMED = "fact_confirmed"
    CONTRADICTION_RECORDED = "contradiction_recorded"
    ENTITY_ADDED = "entity_added"
    RELATION_ADDED = "relation_added"
    ENTITY_MERGED = "entity_merged"
    ENTITY_SPLIT = "entity_split"
    DECISION_RECORDED = "decision_recorded"
    EPISODE_RECORDED = "episode_recorded"


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """A logical change to append. ``seq``/hashes are assigned at seal time."""

    op: str
    ts: str
    tenant: str
    namespace: str
    actor: str  # agent id
    principal: str | None
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerRecord:
    """A sealed, persisted ledger entry."""

    seq: int
    ts: str
    op: str
    tenant: str
    namespace: str
    actor: str
    principal: str | None
    payload: Mapping[str, Any]
    content_hash: str
    prev_hash: str
    entry_hash: str
    meta: dict[str, Any] = field(default_factory=dict)

    def header(self) -> dict[str, Any]:
        """The fields the entry_hash commits to (everything but the entry_hash itself)."""
        return {
            "seq": self.seq,
            "ts": self.ts,
            "op": self.op,
            "tenant": self.tenant,
            "namespace": self.namespace,
            "actor": self.actor,
            "principal": self.principal,
            "content_hash": self.content_hash,
            "prev_hash": self.prev_hash,
        }


def content_hash(op: str, payload: Mapping[str, Any]) -> str:
    """Deterministic hash of an event's semantic content."""
    return hash_obj({"op": op, "payload": payload})


def seal(*, seq: int, event: Event, prev_hash: str) -> LedgerRecord:
    """Compute hashes and produce the persisted :class:`LedgerRecord`.

    The payload is snapshotted through canonical JSON so the record owns a fully isolated,
    normalized copy: later mutations of any projected object can never reach back and alter
    a sealed payload (which would silently break integrity verification).
    """
    payload_snapshot = json.loads(canonical_json(event.payload))
    ch = content_hash(event.op, payload_snapshot)
    header = {
        "seq": seq,
        "ts": event.ts,
        "op": event.op,
        "tenant": event.tenant,
        "namespace": event.namespace,
        "actor": event.actor,
        "principal": event.principal,
        "content_hash": ch,
        "prev_hash": prev_hash,
    }
    entry_hash = sha256_hex(canonical_json(header))
    return LedgerRecord(
        seq=seq,
        ts=event.ts,
        op=event.op,
        tenant=event.tenant,
        namespace=event.namespace,
        actor=event.actor,
        principal=event.principal,
        payload=payload_snapshot,
        content_hash=ch,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )


def verify_chain(
    records: Iterable[LedgerRecord],
    *,
    expected_count: int | None = None,
    expected_head: str | None = None,
) -> int:
    """Verify hash linkage and per-record content/header hashes. Returns the count verified.

    Detects, with no external state: payload edits, header edits (tenant/ts/actor/...),
    mid-chain removals and reorders (seq gaps), duplicates, ``prev_hash`` swaps, and forged
    inserts that were not fully re-chained.

    A bare hash chain is **tamper-evident, not immutable**: tail-truncation and a complete
    re-chained rewrite are only detectable against an external anchor. Pass ``expected_count``
    and/or ``expected_head`` (e.g. persisted elsewhere or pinned by the caller) to catch those.
    Raises :class:`IntegrityError` on the first inconsistency (fail closed).
    """
    prev = GENESIS_HASH
    expected_seq = 1
    count = 0
    last_hash = GENESIS_HASH
    for rec in records:
        if rec.seq != expected_seq:
            raise IntegrityError(f"ledger seq gap: expected {expected_seq}, got {rec.seq}")
        if rec.prev_hash != prev:
            raise IntegrityError(f"ledger chain break at seq {rec.seq}: prev_hash mismatch")
        recomputed_content = content_hash(rec.op, rec.payload)
        if recomputed_content != rec.content_hash:
            raise IntegrityError(f"ledger payload tampered at seq {rec.seq}")
        recomputed_entry = sha256_hex(canonical_json(rec.header()))
        if recomputed_entry != rec.entry_hash:
            raise IntegrityError(f"ledger header tampered at seq {rec.seq}")
        prev = rec.entry_hash
        last_hash = rec.entry_hash
        expected_seq += 1
        count += 1
    if expected_count is not None and count != expected_count:
        raise IntegrityError(f"ledger length mismatch: expected {expected_count}, got {count}")
    if expected_head is not None and last_hash != expected_head:
        raise IntegrityError("ledger head mismatch: chain does not end at the expected head")
    return count
