"""Retrieval receipts — proving what the system *showed*, not just what it stored.

The hash chain proves what was written. It says nothing about what a given agent was handed at a
given moment, and that is the gap that matters when a decision is questioned later: "which context
did it see?" cannot be answered by re-running the query, because the store has moved on.

A :class:`RetrievalReceipt` seals one retrieval: the query, the projection it ran against, the
scorer and weights that ranked it, the ordered results with their scores, and the evidence and
documents behind each one. It is verifiable, chainable and tamper-evident using only ``hashlib``
and ``hmac`` — no service, no ledger of its own, no new dependency.

**Determinism.** The hash covers a canonical *payload* that excludes wall-clock time. Execution
metadata (when it ran, how long it took) travels alongside the payload and is deliberately outside
the digest, so the same query against the same projection seals to the same bytes (mission §14).

**A receipt is not an authority.** It records that a retrieval returned these candidates in this
order. Whether any of them is true remains a question for evidence, review and governance. Sealing
a retrieval must never be mistaken for accepting its contents.
"""

from __future__ import annotations

import hmac
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ._util import canonical_json, hash_obj, new_id, sha256_hex
from .errors import IntegrityError, ValidationError

__all__ = [
    "RECEIPT_VERSION",
    "RetrievalReceipt",
    "ReceiptChain",
    "SCORER_VERSION",
]

#: Bumped when the receipt payload layout changes. A verifier that does not know a version must
#: refuse rather than guess, so old receipts never validate against new rules by accident.
RECEIPT_VERSION = 1

#: Identifies the ranking implementation a receipt was produced by. Two receipts with different
#: scorer versions are not comparable, and saying so explicitly is cheaper than discovering it.
SCORER_VERSION = "epistemos.retrieval/1"


@dataclass(frozen=True, slots=True)
class RetrievalReceipt:
    """An immutable, verifiable record of one authorized retrieval.

    ``payload`` is everything the digest covers. ``execution`` is everything it deliberately does
    not: timestamps and timings, which vary between identical runs and would destroy replayability
    if they were sealed.
    """

    receipt_id: str
    tenant: str
    namespace: str
    agent: str
    query_hash: str
    projection_version: int
    scorer_version: str
    lexical_variant: str
    weights: Mapping[str, float]
    results: tuple[Mapping[str, Any], ...]
    receipt_hash: str
    previous_receipt_hash: str | None = None
    execution: Mapping[str, Any] = field(default_factory=dict)
    signature: str | None = None

    # -- construction --------------------------------------------------------

    @staticmethod
    def canonical_payload(
        *,
        tenant: str,
        namespace: str,
        agent: str,
        query_hash: str,
        projection_version: int,
        scorer_version: str,
        lexical_variant: str,
        weights: Mapping[str, float],
        results: Sequence[Mapping[str, Any]],
        previous_receipt_hash: str | None,
    ) -> dict[str, Any]:
        """The exact structure the digest is taken over. Deliberately excludes time."""
        return {
            "receipt_version": RECEIPT_VERSION,
            "tenant": tenant,
            "namespace": namespace,
            "agent": agent,
            "query_hash": query_hash,
            "projection_version": int(projection_version),
            "scorer_version": scorer_version,
            # Which lexical representation produced these candidates. E-2 measured the same
            # scorer returning materially different rankings under different tokenizers
            # (morphology nDCG@10 0.056 -> 0.904), so a receipt that omitted this would name the
            # ranking function while hiding the input to it — and could not be replayed.
            "lexical_variant": lexical_variant,
            "weights": {k: float(v) for k, v in sorted(weights.items())},
            "results": [dict(r) for r in results],
            "previous_receipt_hash": previous_receipt_hash,
        }

    @classmethod
    def seal(
        cls,
        *,
        tenant: str,
        namespace: str,
        agent: str,
        query: str,
        projection_version: int,
        weights: Mapping[str, float],
        results: Sequence[Mapping[str, Any]],
        lexical_variant: str,
        scorer_version: str = SCORER_VERSION,
        previous: RetrievalReceipt | None = None,
        execution: Mapping[str, Any] | None = None,
        secret: bytes | None = None,
    ) -> RetrievalReceipt:
        """Seal a retrieval. ``secret`` adds an HMAC so a holder of the key can prove authorship;
        without it the receipt is still tamper-evident, just not attributable."""
        if not isinstance(query, str):
            raise ValidationError("query must be a string")
        prev_hash = previous.receipt_hash if previous is not None else None
        payload = cls.canonical_payload(
            tenant=tenant, namespace=namespace, agent=agent,
            query_hash=sha256_hex(query), projection_version=projection_version,
            scorer_version=scorer_version, lexical_variant=lexical_variant,
            weights=weights, results=results, previous_receipt_hash=prev_hash,
        )
        digest = hash_obj(payload)
        sig = None
        if secret is not None:
            sig = hmac.new(secret, canonical_json(payload).encode("utf-8"), "sha256").hexdigest()
        return cls(
            receipt_id=new_id("rcpt"),
            tenant=tenant,
            namespace=namespace,
            agent=agent,
            query_hash=payload["query_hash"],
            projection_version=int(projection_version),
            scorer_version=scorer_version,
            lexical_variant=lexical_variant,
            weights=payload["weights"],
            results=tuple(payload["results"]),
            receipt_hash=digest,
            previous_receipt_hash=prev_hash,
            execution=dict(execution or {}),
            signature=sig,
        )

    # -- verification --------------------------------------------------------

    def payload(self) -> dict[str, Any]:
        return self.canonical_payload(
            tenant=self.tenant, namespace=self.namespace, agent=self.agent,
            query_hash=self.query_hash, projection_version=self.projection_version,
            scorer_version=self.scorer_version, lexical_variant=self.lexical_variant,
            weights=self.weights, results=self.results,
            previous_receipt_hash=self.previous_receipt_hash,
        )

    def verify(self, *, secret: bytes | None = None) -> bool:
        """Recompute the digest (and the HMAC when a key is supplied). Any edit to any sealed
        field changes the digest, so tampering is detected rather than argued about."""
        if hash_obj(self.payload()) != self.receipt_hash:
            return False
        if secret is not None:
            if self.signature is None:
                return False
            expected = hmac.new(
                secret, canonical_json(self.payload()).encode("utf-8"), "sha256"
            ).hexdigest()
            return hmac.compare_digest(expected, self.signature)
        return True

    def matches_query(self, query: str) -> bool:
        """Constant-time check that this receipt sealed exactly this query text."""
        return hmac.compare_digest(sha256_hex(query), self.query_hash)

    # -- serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d = self.payload()
        d.update({
            "receipt_id": self.receipt_id,
            "receipt_hash": self.receipt_hash,
            "execution": dict(self.execution),
        })
        if self.signature is not None:
            d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> RetrievalReceipt:
        version = d.get("receipt_version")
        if version != RECEIPT_VERSION:
            # Refuse rather than best-effort: a verifier that guesses at an unknown layout can
            # report "valid" for something it did not actually understand.
            raise IntegrityError(f"unsupported receipt_version {version!r}")
        return cls(
            receipt_id=str(d["receipt_id"]),
            tenant=str(d["tenant"]),
            namespace=str(d["namespace"]),
            agent=str(d["agent"]),
            query_hash=str(d["query_hash"]),
            projection_version=int(d["projection_version"]),
            scorer_version=str(d["scorer_version"]),
            lexical_variant=str(d["lexical_variant"]),
            weights=dict(d["weights"]),
            results=tuple(dict(r) for r in d["results"]),
            receipt_hash=str(d["receipt_hash"]),
            previous_receipt_hash=d.get("previous_receipt_hash"),
            execution=dict(d.get("execution") or {}),
            signature=d.get("signature"),
        )


@dataclass(slots=True)
class ReceiptChain:
    """An append-only sequence of receipts, each linked to the one before it.

    Linking matters for a reason a single receipt cannot cover: an individually valid receipt says
    nothing about whether *other* receipts were removed. The chain makes a deletion detectable,
    because the surviving links no longer meet.
    """

    receipts: list[RetrievalReceipt] = field(default_factory=list)

    @property
    def head(self) -> RetrievalReceipt | None:
        return self.receipts[-1] if self.receipts else None

    def append(self, receipt: RetrievalReceipt) -> RetrievalReceipt:
        expected = self.head.receipt_hash if self.head else None
        if receipt.previous_receipt_hash != expected:
            raise IntegrityError(
                f"receipt does not link to the chain head: expected previous "
                f"{expected!r}, got {receipt.previous_receipt_hash!r}"
            )
        self.receipts.append(receipt)
        return receipt

    def verify(self, *, secret: bytes | None = None) -> int:
        """Verify every receipt and every link. Returns the count verified; raises on the first
        break, naming the position, so a failure points at where the history diverged."""
        prev: str | None = None
        for i, r in enumerate(self.receipts):
            if not r.verify(secret=secret):
                raise IntegrityError(f"receipt {i} ({r.receipt_id}) failed hash verification")
            if r.previous_receipt_hash != prev:
                raise IntegrityError(
                    f"chain broken at receipt {i} ({r.receipt_id}): expected previous "
                    f"{prev!r}, got {r.previous_receipt_hash!r}"
                )
            prev = r.receipt_hash
        return len(self.receipts)
