"""BITEMPORAL_SEMANTICS gate (mission §10, checkpoint C).

Proven semantically, not by field presence: valid-time queries, transaction-time queries,
retroactive correction, and point-in-time reconstruction ("what did the system know at T?").
"""

from __future__ import annotations

from epistemos import Engine, Principal


def test_caso1_valid_time_axis(engine: Engine, ctx: Principal) -> None:
    src = engine.add_source(ctx, uri="mem://hr", trust=0.9)
    engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Alpha",
                       valid_from="2026-01-01", valid_to="2026-02-01", source=src.id)
    engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Beta",
                       valid_from="2026-02-01", source=src.id)

    assert engine.as_of(ctx, "2026-01-15", subject="Alice", predicate="works_at") == "Alpha"
    assert engine.as_of(ctx, "2026-03-01", subject="Alice", predicate="works_at") == "Beta"
    # "now" (clock is 2026-06) -> the open-ended Beta interval
    assert engine.current(ctx, subject="Alice", predicate="works_at") == "Beta"


def test_caso2_retroactive_correction_separates_axes(engine: Engine, ctx: Principal) -> None:
    src = engine.add_source(ctx, uri="mem://hr", trust=0.9)
    # T1: system is told Alice was at Alpha since January.
    f1 = engine.assert_fact(ctx, subject="Alice", predicate="works_at", object="Alpha",
                            valid_from="2026-01-01", source=src.id)
    t1 = f1.tx_from

    # T3: we discover the January info was WRONG — she was actually at Zeta since January.
    engine.supersede(ctx, f1.id,
                     new={"object": "Zeta", "valid_from": "2026-01-01"},
                     reason="correction: was Zeta all along")

    # transaction-time query: what did the system BELIEVE at T1 about valid-time Jan-15?
    assert engine.as_of(ctx, "2026-01-15", subject="Alice", predicate="works_at", at_tx=t1) == "Alpha"
    # what is NOW believed about valid-time Jan-15?
    assert engine.as_of(ctx, "2026-01-15", subject="Alice", predicate="works_at") == "Zeta"


def test_point_in_time_before_any_knowledge_is_empty(engine: Engine, ctx: Principal) -> None:
    engine.assert_fact(ctx, subject="Bob", predicate="role", object="eng", valid_from="2026-01-01")
    # A transaction time before the system knew anything: it knew nothing.
    assert engine.as_of(ctx, "2026-01-15", subject="Bob", predicate="role",
                        at_tx="2020-01-01T00:00:00Z") is None


def test_future_fact_not_current_until_valid(engine: Engine, ctx: Principal) -> None:
    # A fact whose validity starts in the future of the clock (clock is 2026-06).
    engine.assert_fact(ctx, subject="Carol", predicate="title", object="VP",
                       valid_from="2027-01-01")
    assert engine.current(ctx, subject="Carol", predicate="title") is None
    assert engine.as_of(ctx, "2027-06-01", subject="Carol", predicate="title") == "VP"
