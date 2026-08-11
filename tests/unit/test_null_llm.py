"""NULL_LLM_MODE gate (checkpoint K).

The whole core runs with NullModelProvider; enrichment methods fail loudly so no code path
can silently depend on a model.
"""

from __future__ import annotations

import pytest

from epistemos import Engine, NullModelProvider, Principal
from epistemos.providers import ModelUnavailableError


def test_null_provider_reports_unavailable_and_refuses() -> None:
    p = NullModelProvider()
    assert p.available() is False
    with pytest.raises(ModelUnavailableError):
        p.embed(["x"])
    with pytest.raises(ModelUnavailableError):
        p.extract_triples("x")
    with pytest.raises(ModelUnavailableError):
        p.summarize("x")


def test_full_core_flow_without_any_model(engine: Engine, ctx: Principal) -> None:
    # No provider is passed to the engine at all; all core ops still work.
    src = engine.add_source(ctx, uri="mem://s")
    f = engine.assert_fact(ctx, subject="A", predicate="p", object="B", source=src.id)
    engine.supersede(ctx, f.id, new={"object": "C"})
    assert engine.current(ctx, subject="A", predicate="p") == "C"
    assert engine.timeline(ctx, subject="A")
    assert engine.search(ctx, text="A p")
    assert engine.explain(ctx, f.id)["id"] == f.id
    assert engine.verify_integrity() == engine.store.event_count()
    dump = engine.export()
    assert dump["event_count"] == engine.store.event_count()
