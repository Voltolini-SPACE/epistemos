"""Collaborative claims: the verifiable epistemology layer (EPISTEMOS-05).

The v0.4 core answers *"what do we know?"* and shares it by permission. This layer adds the
distinction the mission insists on:

    CONTRIBUTION != TRUTH

A **Claim** is a proposition someone asserted — it *exists* independently of whether the system
*believes* it. **Evidence** supports/contradicts/weakens claims. **Reviews** are individual,
preserved assessments. **Belief** is a *derived, auditable* state (never a stored boolean), and
**acceptance** is a governed act (a policy decision), never a vote count.

These are new object kinds that **reuse** the existing machinery — `Envelope` (owner, tenant,
namespace, `spaces`, source, confidence, derivation edges), the hash-chained ledger, the bitemporal
helpers, the Knowledge-Spaces firewall and `explain()`. They do not duplicate `Fact`: a Fact is a
believed statement in the knowledge graph; a Claim is a contribution in the *claim graph* that may,
after review and a governed acceptance, produce accepted knowledge. (ADR-028.)

Identities stay separate (mission §3): ``owner`` = the *ingesting agent*, ``claimant`` = *who
asserts it* (may be a human/other identity), ``source`` = the *external origin*. Reviewer identity
is the ``owner`` of a Review. None are collapsed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from .._util import parse_instant
from ..errors import TemporalError, ValidationError
from ..model import SCHEMA_VERSION, Envelope

__all__ = [
    "ClaimStatus",
    "BeliefState",
    "Verdict",
    "EvidenceRelation",
    "EvidenceKind",
    "ContributorKind",
    "Claim",
    "Evidence",
    "Review",
]


class ClaimStatus(StrEnum):
    """The lifecycle status stored on a claim (distinct from the *derived* belief)."""

    OPEN = "open"  # asserted, live
    RETRACTED = "retracted"  # withdrawn by the claimant/owner (history preserved)
    SUPERSEDED = "superseded"  # replaced by a newer claim


class BeliefState(StrEnum):
    """The DERIVED epistemic state of a claim (computed from reviews + policy; never stored as a
    bare boolean). Every value is explainable via ``explain_claim`` (WHY_*)."""

    PROPOSED = "proposed"  # no review yet
    SUPPORTED = "supported"  # confirmations, no live disputes
    DISPUTED = "disputed"  # at least one live dispute coexists
    ACCEPTED = "accepted"  # a governed acceptance under policy (NOT a vote)
    REJECTED = "rejected"  # a governed rejection under policy
    RETRACTED = "retracted"  # the claim was withdrawn
    SUPERSEDED = "superseded"  # the claim was superseded


class Verdict(StrEnum):
    """A reviewer's individual assessment. Preserved verbatim; majority is not truth (§9)."""

    CONFIRM = "confirm"
    DISPUTE = "dispute"
    REJECT = "reject"
    REQUEST_EVIDENCE = "request_evidence"
    ABSTAIN = "abstain"


class EvidenceRelation(StrEnum):
    """How a piece of evidence relates to a claim. 'attached' does NOT mean 'supports' (§6)."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    WEAKENS = "weakens"
    DERIVED_FROM = "derived_from"


class EvidenceKind(StrEnum):
    DOCUMENT = "document"
    URI = "uri"
    HASH = "hash"
    OBSERVATION = "observation"
    DATASET = "dataset"
    ARTIFACT = "artifact"
    EVENT = "event"
    EXTERNAL_RECORD = "external_record"


class ContributorKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SERVICE = "service"
    ORGANIZATION = "organization"


def _tuple(value: Sequence[str] | None) -> tuple[str, ...]:
    return () if value is None else tuple(str(v) for v in value)


@dataclass(frozen=True, slots=True, kw_only=True)
class Claim(Envelope):
    """A proposition asserted by a claimant — it exists whether or not the system believes it.

    ``owner`` (Envelope) is the ingesting agent; ``claimant`` is who asserts it; ``source``
    (Envelope) is the external origin — three distinct identities (§3). Bitemporal like a Fact.
    """

    kind: str = "claim"
    subject: str
    predicate: str
    object: str | None = None  # noqa: A002
    claimant: str
    contributor_kind: str = ContributorKind.AGENT.value
    valid_from: str | None = None
    valid_to: str | None = None
    tx_from: str
    tx_to: str | None = None
    status: str = ClaimStatus.OPEN.value

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.subject or not self.predicate:
            raise ValidationError("claim requires non-empty subject and predicate")
        if not self.claimant:
            raise ValidationError("claim requires a claimant")
        vf, vt = parse_instant(self.valid_from), parse_instant(self.valid_to)
        if vf is not None and vt is not None and vt < vf:
            raise TemporalError(f"valid_to {self.valid_to} precedes valid_from {self.valid_from}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Claim:
        return cls(**{k: v for k, v in d.items() if k in _CLAIM_FIELDS})


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence(Envelope):
    """A typed artifact that relates to claims. The full content need not be stored — a URI plus a
    content hash is a valid, integrity-checkable reference (§5). Space-scoped like any object."""

    kind: str = "evidence"
    evidence_kind: str = EvidenceKind.URI.value
    title: str | None = None
    uri: str | None = None
    content_hash: str | None = None
    origin: str | None = None  # where the evidence itself came from (may differ from the claim)
    captured_at: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            EvidenceKind(self.evidence_kind)
        except ValueError:
            raise ValidationError(f"unknown evidence_kind {self.evidence_kind!r}") from None
        if self.captured_at is not None:
            parse_instant(self.captured_at)  # validate

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Evidence:
        return cls(**{k: v for k, v in d.items() if k in _EVIDENCE_FIELDS})


@dataclass(frozen=True, slots=True, kw_only=True)
class Review(Envelope):
    """One reviewer's individual, preserved assessment of a claim. ``owner`` is the reviewer."""

    kind: str = "review"
    claim_id: str
    verdict: str
    rationale: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.claim_id:
            raise ValidationError("review requires a claim_id")
        try:
            Verdict(self.verdict)
        except ValueError:
            raise ValidationError(f"unknown verdict {self.verdict!r}") from None
        object.__setattr__(self, "evidence_refs", _tuple(self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Review:
        return cls(**{k: v for k, v in d.items() if k in _REVIEW_FIELDS})


def _field_names(cls: type) -> frozenset[str]:
    from dataclasses import fields as _dc_fields

    return frozenset(f.name for f in _dc_fields(cls))


_CLAIM_FIELDS = _field_names(Claim)
_EVIDENCE_FIELDS = _field_names(Evidence)
_REVIEW_FIELDS = _field_names(Review)

_ = SCHEMA_VERSION  # claims share the store schema version
