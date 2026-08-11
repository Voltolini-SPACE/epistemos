"""CONTRADICTION_PRESERVES_HISTORY gate (checkpoint D).

assert / confirm / supersede / contradict / retract are distinct states, each producing
lineage, and none hard-deletes the past. superseded != contradicted != retracted != deleted.
"""

from __future__ import annotations

from epistemos import BeliefStatus, Engine, Principal


def test_supersede_keeps_old_fact_and_links(engine: Engine, ctx: Principal) -> None:
    f1 = engine.assert_fact(ctx, subject="A", predicate="p", object="X")
    f2 = engine.supersede(ctx, f1.id, new={"object": "Y"})
    old = engine.get(ctx, f1.id)
    assert old is not None  # not deleted
    assert old.status == BeliefStatus.SUPERSEDED
    assert old.tx_to is not None  # belief ended
    assert f2.supersedes == (f1.id,)
    assert f2.believed is True
    assert engine.current(ctx, subject="A", predicate="p") == "Y"


def test_retract_differs_from_supersede(engine: Engine, ctx: Principal) -> None:
    f = engine.assert_fact(ctx, subject="A", predicate="p", object="X")
    engine.retract(ctx, f.id, reason="withdrawn")
    got = engine.get(ctx, f.id)
    assert got.status == BeliefStatus.RETRACTED  # not superseded
    assert got.tx_to is not None
    assert engine.current(ctx, subject="A", predicate="p") is None  # no replacement


def test_contradict_changes_neither_belief(engine: Engine, ctx: Principal) -> None:
    f1 = engine.assert_fact(ctx, subject="A", predicate="p", object="X")
    f2 = engine.assert_fact(ctx, subject="A", predicate="p", object="Y")
    engine.contradict(ctx, f1.id, by=f2.id, note="conflict")
    g1, g2 = engine.get(ctx, f1.id), engine.get(ctx, f2.id)
    # both still believed (contradiction does not overwrite)
    assert g1.believed and g2.believed
    assert g1.status == BeliefStatus.ASSERTED and g2.status == BeliefStatus.ASSERTED
    # symmetric contradiction edge recorded
    assert f2.id in g1.contradicts and f1.id in g2.contradicts


def test_confirm_raises_confidence_and_records_corroboration(
    engine: Engine, ctx: Principal
) -> None:
    s2 = engine.add_source(ctx, uri="mem://second", trust=0.9)
    f = engine.assert_fact(ctx, subject="A", predicate="p", object="X", confidence=0.5)
    updated = engine.confirm(ctx, f.id, source=s2.id, delta_confidence=0.3)
    assert abs(updated.confidence - 0.8) < 1e-9
    assert updated.metadata["corroborations"][0]["source"] == s2.id


def test_no_hard_delete_api_exists(engine: Engine, ctx: Principal) -> None:
    # There is intentionally no delete/erase method on the engine.
    for name in ("delete", "erase", "hard_delete", "drop_fact", "remove"):
        assert not hasattr(engine, name), f"unexpected destructive method {name!r}"


def test_all_states_leave_history_in_ledger(engine: Engine, ctx: Principal) -> None:
    f = engine.assert_fact(ctx, subject="A", predicate="p", object="X")
    engine.confirm(ctx, f.id, source=engine.add_source(ctx, uri="mem://s").id)
    engine.retract(ctx, f.id)
    ops = [r.op for r in engine.store.read_events()]
    assert "fact_asserted" in ops and "fact_confirmed" in ops and "fact_retracted" in ops
    # verify chain intact after the sequence
    assert engine.verify_integrity() == engine.store.event_count()
