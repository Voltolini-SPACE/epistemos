"""TEMPORAL_INDEX_QUERY gate (ETAPA 13).

The index stores ALL temporal versions; the retriever applies temporal filtering. So historical
(as_of valid), transaction-time, current, and believed-only text search all work through FTS.
"""

from __future__ import annotations

from epistemos import Engine, Principal


def test_current_vs_historical_text_search(fts: Engine, ctx: Principal) -> None:
    src = fts.add_source(ctx, uri="mem://hr", trust=0.9)
    f1 = fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Alpha",
                         valid_from="2026-01-01", valid_to="2026-02-01", source=src.id)
    fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Beta",
                    valid_from="2026-02-01", source=src.id)

    # believed_only text search: both facts are believed (Alpha ended by validity, not belief)
    believed = fts.search(ctx, text="Alice", believed_only=True, limit=20)
    assert {r["id"] for r in believed} >= {f1.id}

    # temporal component marks Alpha historical (not valid now) and Beta current
    now = fts.search(ctx, text="Alice", limit=20)
    tstate = {r["id"]: r["score_components"].get("temporal") for r in now if r["kind"] == "fact"}
    assert tstate[f1.id] == 0.0  # Alpha not valid now
    beta_id = next(r["id"] for r in now if r["temporal_state"]
                   and r["temporal_state"]["valid_from"] == "2026-02-01")
    assert tstate[beta_id] == 1.0


def test_as_of_valid_time_text_search(fts: Engine, ctx: Principal) -> None:
    src = fts.add_source(ctx, uri="mem://hr", trust=0.9)
    f1 = fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Alpha",
                         valid_from="2026-01-01", valid_to="2026-02-01", source=src.id)
    # at 2026-01-15, Alpha was valid -> temporal contribution = 1
    hist = fts.search(ctx, text="Alice", at_valid="2026-01-15", limit=20)
    tmap = {r["id"]: r["score_components"].get("temporal") for r in hist}
    assert tmap[f1.id] == 1.0


def test_retroactive_correction_tx_time_search(fts: Engine, ctx: Principal) -> None:
    src = fts.add_source(ctx, uri="mem://hr", trust=0.9)
    f1 = fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Zephyr",
                         valid_from="2026-01-01", source=src.id)
    t1 = f1.tx_from
    fts.supersede(ctx, f1.id, new={"object": "Zenith", "valid_from": "2026-01-01"})
    # searching text at transaction-time t1 (about valid 2026-01-15): original belief only
    at_t1 = fts.search(ctx, text="Alice", at_tx=t1, at_valid="2026-01-15", limit=20)
    believed = {r["id"] for r in at_t1 if r["score_components"].get("temporal") == 1.0}
    assert f1.id in believed  # the original fact was believed at t1
