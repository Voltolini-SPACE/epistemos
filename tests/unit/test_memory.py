"""MEMORY_TAXONOMY gate (checkpoint I).

Memory classes are real semantic types with defined scope/retention/mutability/temporal/
provenance semantics, not decorative labels — asserted against the machine-readable spec.
"""

from __future__ import annotations

import pytest

from epistemos import Engine, MemoryClass, Principal
from epistemos.memory import SPEC, spec_for


def test_spec_distinguishes_classes() -> None:
    working = spec_for(MemoryClass.WORKING)
    semantic = spec_for(MemoryClass.SEMANTIC)
    episodic = spec_for(MemoryClass.EPISODIC)
    # distinctions are real, not decorative
    assert working.mutable is True and semantic.mutable is False
    assert working.temporal is False and semantic.temporal is True
    assert episodic.provenance_required is True and working.provenance_required is False
    assert semantic.scope != working.scope


def test_all_classes_have_specs() -> None:
    for mc in MemoryClass:
        assert mc.value in SPEC


def test_spec_for_unknown_fails_closed() -> None:
    with pytest.raises(ValueError):
        spec_for("telepathic")


def test_recall_filters_by_class(engine: Engine, ctx: Principal) -> None:
    engine.assert_fact(ctx, subject="A", predicate="p", object="B",
                       memory_class=MemoryClass.SEMANTIC.value)
    engine.assert_fact(ctx, subject="proc", predicate="step", object="1",
                       memory_class=MemoryClass.PROCEDURAL.value)
    engine.remember(ctx, summary="the meeting happened", session="s1")

    semantic = engine.recall(ctx, memory_class=MemoryClass.SEMANTIC.value)
    assert all(o.get("memory_class") == "semantic" for o in semantic)
    assert semantic, "expected at least one semantic memory"

    procedural = engine.recall(ctx, memory_class=MemoryClass.PROCEDURAL.value)
    assert all(o.get("memory_class") == "procedural" for o in procedural)

    episodic = engine.recall(ctx, memory_class=MemoryClass.EPISODIC.value)
    assert any(o.get("kind") == "episode" for o in episodic)


def test_recall_filters_by_session(engine: Engine, ctx: Principal) -> None:
    engine.remember(ctx, summary="episode one", session="s1")
    engine.remember(ctx, summary="episode two", session="s2")
    only_s1 = engine.recall(ctx, session="s1")
    assert all(o.get("session") == "s1" for o in only_s1)
    assert len(only_s1) == 1
