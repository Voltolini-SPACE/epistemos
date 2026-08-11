"""Fallback & health-state gate (ETAPA 8, ADR-019).

The index exposes explicit states and NEVER masks a broken index with silent stale data: when the
index is not HEALTHY, search falls back to the correct O(N) scan.
"""

from __future__ import annotations

from epistemos import Engine, Principal
from epistemos.storage import MemoryStore


def test_health_reports_index_state(fts: Engine, ctx: Principal) -> None:
    fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme")
    h = fts.health(ctx, verify=True)
    assert h["index"]["state"] == "INDEX_HEALTHY"
    assert h["index"]["backend"] == "sqlite-fts5"
    assert h["index"]["consistent"] is True


def test_degraded_index_falls_back_to_correct_scan(fts: Engine, ctx: Principal) -> None:
    fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme")
    fts.assert_fact(ctx, subject="Bob", predicate="works_at", object="Globex")
    # force DEGRADED: search must NOT trust the index; it falls back to the scan (correct)
    fts.lexical_index.mark_degraded()
    assert fts.health(ctx)["index"]["state"] == "INDEX_DEGRADED"
    res = fts.search(ctx, text="Alice Acme", limit=5)
    assert res and res[0]["retrieval_method"].startswith("scan-tfidf")  # fell back, correct results
    assert any(r["kind"] == "fact" for r in res)


def test_degraded_index_never_returns_stale_incomplete(fts: Engine, ctx: Principal) -> None:
    # Mark degraded, THEN add a fact. A degraded FTS index would miss it; the fallback scan
    # reads live authoritative state, so the new fact is still found.
    fts.lexical_index.mark_degraded()
    fts.assert_fact(ctx, subject="Zara", predicate="p", object="freshvalue")
    # "freshvalue" is unique to Zara's fact; a non-empty result proves the fallback found it
    res = fts.search(ctx, text="freshvalue", limit=5)
    assert res  # found via fallback despite the degraded index
    assert res[0]["retrieval_method"].startswith("scan-tfidf")


def test_memory_backend_reports_scan(ctx: Principal) -> None:
    eng = Engine(MemoryStore())
    eng.assert_fact(ctx, subject="Alice", predicate="p", object="x")
    h = eng.health(ctx)
    assert h["index"]["state"] == "INDEX_UNAVAILABLE"
    assert h["index"]["backend"] == "scan"
    # search still works (scan), verify_index_consistency is trivially True
    assert eng.search(ctx, text="Alice")
    assert eng.verify_index_consistency() is True


def test_rebuild_restores_healthy(fts: Engine, ctx: Principal) -> None:
    fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme")
    fts.lexical_index.mark_degraded()
    assert fts.health(ctx)["index"]["state"] == "INDEX_DEGRADED"
    fts.rebuild_index()
    assert fts.health(ctx)["index"]["state"] == "INDEX_HEALTHY"
    assert fts.verify_index_consistency()
