"""EPISTEMOS core data model (mission §9).

Every persisted object shares an :class:`Envelope`: identity, scope (tenant/namespace),
ownership, transaction time, provenance links, and supersession/contradiction/derivation
edges. :class:`Fact` additionally carries **bitemporal** time — *valid time* (when the
statement is true in the world) and *transaction time* (when the system believed it).

The dataclasses are the typed boundary; internally the engine and stores exchange plain
JSON-able dicts (``to_dict`` / ``from_dict``). Fields are validated on construction; no
field exists without a reason (mission: "não criar campos arbitrariamente").
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from .._util import parse_instant
from ..errors import TemporalError, ValidationError

__all__ = [
    "Kind",
    "BeliefStatus",
    "MemoryClass",
    "Envelope",
    "Fact",
    "Source",
    "Entity",
    "Relation",
    "Decision",
    "Episode",
    "Observation",
    "Document",
]

SCHEMA_VERSION = 1


class Kind(StrEnum):
    ENTITY = "entity"
    RELATION = "relation"
    FACT = "fact"
    SOURCE = "source"
    DOCUMENT = "document"
    OBSERVATION = "observation"
    DECISION = "decision"
    EPISODE = "episode"


class BeliefStatus(StrEnum):
    ASSERTED = "asserted"  # currently believed (tx_to open)
    SUPERSEDED = "superseded"  # belief ended, replaced by a newer fact
    RETRACTED = "retracted"  # belief withdrawn, no replacement


class MemoryClass(StrEnum):
    """Semantic partition of memory (mission §12). Not separate databases — a
    testable, queryable label over the one store."""

    WORKING = "working"  # transient, session-scoped scratch
    SESSION = "session"  # bounded to one session
    EPISODIC = "episodic"  # time-stamped events/experiences
    SEMANTIC = "semantic"  # distilled facts about the world
    PROCEDURAL = "procedural"  # how-to / learned procedures
    LONGTERM = "longterm"  # durable knowledge


def _tuple(value: Sequence[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(str(v) for v in value)


def _clean_meta(meta: Mapping[str, Any] | None) -> dict[str, Any]:
    if meta is None:
        return {}
    if not isinstance(meta, Mapping):
        raise ValidationError("metadata must be a mapping")
    return dict(meta)


@dataclass(frozen=True, slots=True, kw_only=True)
class Envelope:
    id: str
    kind: str
    tenant: str
    namespace: str
    owner: str  # the agent that created the object
    created_at: str  # transaction time (ISO-8601, UTC)
    source: str | None = None  # source id backing this object
    source_hash: str | None = None  # content hash of the backing source payload
    confidence: float = 1.0
    provenance: tuple[str, ...] = ()  # activity ids that produced this object
    supersedes: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    derived_from: tuple[str, ...] = ()
    # Knowledge Spaces (EPISTEMOS-04): the visibility container(s) this object is placed in. Empty
    # means PRIVATE to the owner (the fail-closed default) — no space object required, so the
    # local-first single-agent case needs zero configuration and v0.3 behaviour is reproduced.
    spaces: tuple[str, ...] = ()
    schema_version: int = SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValidationError(f"confidence must be in [0,1], got {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class Fact(Envelope):
    """A bitemporal statement, modeled as a (subject, predicate, object) triple.

    ``object`` may be ``None`` to represent "the relation ended / has no value".
    ``valid_from``/``valid_to`` are the world-time interval (half-open ``[from, to)``).
    ``tx_from``/``tx_to`` are the belief interval; ``tx_to`` open == currently believed.
    """

    kind: str = Kind.FACT.value
    subject: str
    predicate: str
    object: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    tx_from: str  # when asserted into the system
    tx_to: str | None = None  # when belief ended (None == still believed)
    status: str = BeliefStatus.ASSERTED.value
    memory_class: str = MemoryClass.SEMANTIC.value

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.subject or not self.predicate:
            raise ValidationError("fact requires non-empty subject and predicate")
        vf = parse_instant(self.valid_from)
        vt = parse_instant(self.valid_to)
        if vf is not None and vt is not None and vt < vf:
            raise TemporalError(f"valid_to {self.valid_to} precedes valid_from {self.valid_from}")

    @property
    def believed(self) -> bool:
        return self.tx_to is None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Fact:
        return cls(**{k: v for k, v in d.items() if k in _FACT_FIELDS})


@dataclass(frozen=True, slots=True, kw_only=True)
class Source(Envelope):
    kind: str = Kind.SOURCE.value
    uri: str
    source_kind: str = "unknown"  # note | document | api | tool | agent | observation
    trust: float = 0.5  # source authority in [0,1]

    def __post_init__(self) -> None:
        super().__post_init__()
        if not (0.0 <= float(self.trust) <= 1.0):
            raise ValidationError(f"trust must be in [0,1], got {self.trust}")

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Source:
        return cls(**{k: v for k, v in d.items() if k in _SOURCE_FIELDS})


@dataclass(frozen=True, slots=True, kw_only=True)
class Entity(Envelope):
    kind: str = Kind.ENTITY.value
    name: str
    entity_type: str = "thing"
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.name:
            raise ValidationError("entity requires a name")
        object.__setattr__(self, "aliases", _tuple(self.aliases))

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Entity:
        return cls(**{k: v for k, v in d.items() if k in _ENTITY_FIELDS})


@dataclass(frozen=True, slots=True, kw_only=True)
class Relation(Envelope):
    kind: str = Kind.RELATION.value
    source_entity: str
    target_entity: str
    rel_type: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if not (self.source_entity and self.target_entity and self.rel_type):
            raise ValidationError("relation requires source_entity, target_entity, rel_type")

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Relation:
        return cls(**{k: v for k, v in d.items() if k in _RELATION_FIELDS})


@dataclass(frozen=True, slots=True, kw_only=True)
class Decision(Envelope):
    kind: str = Kind.DECISION.value
    statement: str
    evidence: tuple[str, ...] = ()  # fact/observation ids that support the decision
    alternatives: tuple[str, ...] = ()
    outcome: str | None = None
    reversible: bool = True

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.statement:
            raise ValidationError("decision requires a statement")
        object.__setattr__(self, "evidence", _tuple(self.evidence))
        object.__setattr__(self, "alternatives", _tuple(self.alternatives))

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Decision:
        return cls(**{k: v for k, v in d.items() if k in _DECISION_FIELDS})


@dataclass(frozen=True, slots=True, kw_only=True)
class Episode(Envelope):
    """A time-stamped experience — the unit of episodic memory."""

    kind: str = Kind.EPISODE.value
    summary: str
    occurred_at: str
    session: str | None = None
    facts: tuple[str, ...] = ()  # facts distilled from this episode

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "facts", _tuple(self.facts))

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Episode:
        return cls(**{k: v for k, v in d.items() if k in _EPISODE_FIELDS})


@dataclass(frozen=True, slots=True, kw_only=True)
class Observation(Envelope):
    """A raw claim as delivered by a source, before it becomes a believed fact."""

    kind: str = Kind.OBSERVATION.value
    text: str
    session: str | None = None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Observation:
        return cls(**{k: v for k, v in d.items() if k in _OBSERVATION_FIELDS})


@dataclass(frozen=True, slots=True, kw_only=True)
class Document(Envelope):
    kind: str = Kind.DOCUMENT.value
    title: str
    text: str
    mime: str = "text/plain"

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Document:
        return cls(**{k: v for k, v in d.items() if k in _DOCUMENT_FIELDS})


def _field_names(cls: type) -> frozenset[str]:
    # dataclasses.fields on a frozen+slots dataclass; include inherited envelope fields.
    from dataclasses import fields as _dc_fields

    return frozenset(f.name for f in _dc_fields(cls))


_FACT_FIELDS = _field_names(Fact)
_SOURCE_FIELDS = _field_names(Source)
_ENTITY_FIELDS = _field_names(Entity)
_RELATION_FIELDS = _field_names(Relation)
_DECISION_FIELDS = _field_names(Decision)
_EPISODE_FIELDS = _field_names(Episode)
_OBSERVATION_FIELDS = _field_names(Observation)
_DOCUMENT_FIELDS = _field_names(Document)
