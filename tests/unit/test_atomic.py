"""ATOMIC_MUTATION gate (checkpoint B).

Fault injection at every stage of the mutation path proves the invariant:
    STATE_BEFORE == STATE_AFTER  (failed op)   OR   both ledger+projection committed.
Never an intermediate state (ledger written but projection not, or vice-versa).
"""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal


class Boom(RuntimeError):
    pass


def _state(engine: Engine, ctx: Principal) -> tuple[int, dict]:
    objs = {o["id"]: o for o in engine.store.objects(ctx.tenant, ctx.namespace)}
    return engine.store.event_count(), objs


@pytest.mark.parametrize("stage", ["before_ledger", "during_ledger", "during_projection"])
def test_fault_injection_leaves_no_intermediate_state(
    engine: Engine, ctx: Principal, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    # seed one committed fact so "before" state is non-trivial
    src = engine.add_source(ctx, uri="mem://x")
    engine.assert_fact(ctx, subject="A", predicate="p", object="B", source=src.id)
    before = _state(engine, ctx)

    store = engine.store
    if stage == "before_ledger":
        orig = store.append
        monkeypatch.setattr(store, "append", lambda *a, **k: (_ for _ in ()).throw(Boom()))
    elif stage == "during_ledger":
        monkeypatch.setattr(store, "_persist_record",
                            lambda *a, **k: (_ for _ in ()).throw(Boom()))
    else:  # during_projection
        monkeypatch.setattr(store, "put_object",
                            lambda *a, **k: (_ for _ in ()).throw(Boom()))

    with pytest.raises(Boom):
        engine.assert_fact(ctx, subject="C", predicate="p", object="D", source=src.id)

    monkeypatch.undo()
    after = _state(engine, ctx)
    assert before == after, f"stage {stage} left intermediate state"


def test_happy_path_commits_both(engine: Engine, ctx: Principal) -> None:
    ev_before = engine.store.event_count()
    f = engine.assert_fact(ctx, subject="A", predicate="p", object="B")
    # both ledger AND projection advanced together
    assert engine.store.event_count() == ev_before + 1
    assert engine.get(ctx, f.id) is not None


def test_rollback_preserves_integrity(engine: Engine, ctx: Principal,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    engine.add_source(ctx, uri="mem://x")
    n = engine.verify_integrity()
    monkeypatch.setattr(engine.store, "put_object",
                        lambda *a, **k: (_ for _ in ()).throw(Boom()))
    with pytest.raises(Boom):
        engine.assert_fact(ctx, subject="A", predicate="p", object="B")
    monkeypatch.undo()
    # chain still verifies and length is unchanged
    assert engine.verify_integrity() == n
