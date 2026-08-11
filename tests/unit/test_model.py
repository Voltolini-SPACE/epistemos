"""CORE_MODEL gate: envelope fields, validation, (de)serialization."""

from __future__ import annotations

import pytest

from epistemos.errors import TemporalError, ValidationError
from epistemos.model import BeliefStatus, Fact, MemoryClass, Source


def _fact(**kw) -> Fact:
    base = dict(
        id="fact_1", tenant="t", namespace="n", owner="a", created_at="2026-01-01T00:00:00Z",
        subject="Alice", predicate="works_at", object="X", tx_from="2026-01-01T00:00:00Z",
    )
    base.update(kw)
    return Fact(**base)


def test_fact_has_bitemporal_and_envelope_fields() -> None:
    f = _fact(valid_from="2026-01-01", confidence=0.9)
    d = f.to_dict()
    for key in (
        "id", "kind", "tenant", "namespace", "owner", "created_at", "source", "source_hash",
        "confidence", "provenance", "supersedes", "contradicts", "derived_from", "schema_version",
        "metadata", "subject", "predicate", "object", "valid_from", "valid_to", "tx_from", "tx_to",
        "status", "memory_class",
    ):
        assert key in d, key
    assert f.believed is True
    assert d["kind"] == "fact"


def test_fact_roundtrip() -> None:
    f = _fact(valid_from="2026-01-01", metadata={"k": "v"})
    assert Fact.from_dict(f.to_dict()) == f


def test_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        _fact(confidence=1.5)
    with pytest.raises(ValidationError):
        _fact(confidence=-0.1)


def test_valid_interval_ordering() -> None:
    with pytest.raises(TemporalError):
        _fact(valid_from="2026-02-01", valid_to="2026-01-01")


def test_missing_subject_rejected() -> None:
    with pytest.raises(ValidationError):
        _fact(subject="")


def test_source_trust_bounds() -> None:
    with pytest.raises(ValidationError):
        Source(
            id="s", tenant="t", namespace="n", owner="a", created_at="2026-01-01T00:00:00Z",
            uri="mem://x", trust=2.0,
        )


def test_enums_are_str() -> None:
    assert BeliefStatus.ASSERTED == "asserted"
    assert MemoryClass.SEMANTIC == "semantic"
