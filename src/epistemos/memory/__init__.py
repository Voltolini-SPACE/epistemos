"""Memory taxonomy semantics (mission §12, gate MEMORY_TAXONOMY).

Memory classes are **semantic types**, not decorative labels, and they are not separate
databases — they are typed views over the one ledger-backed store, each with defined
scope, retention, mutability, temporal semantics and provenance requirements. This table
is the machine-readable contract that ``docs/spec/MEMORY_MODEL.md`` documents and that
tests assert against, so the distinctions are real and enforceable.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..model import MemoryClass

__all__ = ["MemoryClass", "MemorySpec", "SPEC", "spec_for"]


@dataclass(frozen=True, slots=True)
class MemorySpec:
    memory_class: str
    scope: str  # who/what the memory belongs to
    retention: str  # how long it is expected to live
    mutable: bool  # may its value change in place (vs. append-only history)
    temporal: bool  # does bitemporal validity apply
    provenance_required: bool  # must it carry a source


SPEC: dict[str, MemorySpec] = {
    MemoryClass.WORKING.value: MemorySpec(
        memory_class=MemoryClass.WORKING.value,
        scope="session/agent transient",
        retention="ephemeral (cleared when the session ends)",
        mutable=True,
        temporal=False,
        provenance_required=False,
    ),
    MemoryClass.SESSION.value: MemorySpec(
        memory_class=MemoryClass.SESSION.value,
        scope="single session",
        retention="session lifetime",
        mutable=True,
        temporal=False,
        provenance_required=False,
    ),
    MemoryClass.EPISODIC.value: MemorySpec(
        memory_class=MemoryClass.EPISODIC.value,
        scope="agent",
        retention="durable, append-only",
        mutable=False,
        temporal=True,
        provenance_required=True,
    ),
    MemoryClass.SEMANTIC.value: MemorySpec(
        memory_class=MemoryClass.SEMANTIC.value,
        scope="tenant/namespace shared knowledge",
        retention="durable, superseded not deleted",
        mutable=False,
        temporal=True,
        provenance_required=True,
    ),
    MemoryClass.PROCEDURAL.value: MemorySpec(
        memory_class=MemoryClass.PROCEDURAL.value,
        scope="tenant/namespace",
        retention="durable, versioned",
        mutable=False,
        temporal=True,
        provenance_required=True,
    ),
    MemoryClass.LONGTERM.value: MemorySpec(
        memory_class=MemoryClass.LONGTERM.value,
        scope="tenant",
        retention="durable, superseded not deleted",
        mutable=False,
        temporal=True,
        provenance_required=True,
    ),
}


def spec_for(memory_class: str) -> MemorySpec:
    """Return the semantic spec for a memory class. Fail closed on unknown classes."""
    MemoryClass(memory_class)  # raises ValueError on unknown
    return SPEC[memory_class]
