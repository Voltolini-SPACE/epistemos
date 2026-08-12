"""EPISTEMOS-03 audit: the index's own health signal must be trustworthy.

Findings B-01/OV-02/LT-01 (content-drift invisible to verify), LT-07 (rebuild leaves the index
degraded), LT-02 (self-contradictory health), B-03 (scan query cost uncapped), B-06 (rebuild on
every open). If health() says HEALTHY, search served by the index must be complete; if it cannot
promise that, it must say DEGRADED and fall back.
"""

from __future__ import annotations

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.index import IndexHealth
from epistemos.storage import SQLiteStore

CTX = Principal(tenant="acme", agent="claude", namespace="hr")


@pytest.fixture
def eng(tmp_path) -> Engine:
    return Engine(SQLiteStore(tmp_path / "r.db"), clock=ManualClock())


def test_verify_detects_fts_content_corruption(eng: Engine) -> None:
    """B-01: a corrupted content cell (row still present) must be caught by verify()."""
    s = eng.add_source(CTX, uri="mem://s", trust=0.9)
    eng.assert_fact(CTX, subject="Alice", predicate="p", object="uniquetokenAAA", source=s.id)
    eng.assert_fact(CTX, subject="Bob", predicate="p", object="uniquetokenBBB", source=s.id)
    assert eng.verify_index_consistency() is True
    # corrupt the content of the AAA row without touching the mapping
    eng.store._conn.execute(
        "UPDATE fts_idx SET content='uniquetokenZZZ' WHERE content LIKE '%AAA%'"
    )
    assert eng.verify_index_consistency() is False, "content drift went undetected"
    assert eng.lexical_index.health() is IndexHealth.DEGRADED
    # and because it is now degraded, search falls back to the correct scan
    hits = eng.search(CTX, text="uniquetokenAAA", limit=10)
    assert hits and hits[0]["retrieval_method"].startswith("scan")


def test_health_is_not_self_contradictory(eng: Engine) -> None:
    """LT-02: health(verify=True) must not report HEALTHY together with consistent=False."""
    s = eng.add_source(CTX, uri="mem://s", trust=0.9)
    eng.assert_fact(CTX, subject="A", predicate="p", object="tokenA", source=s.id)
    eng.store._conn.execute("UPDATE fts_idx SET content='tokenX' WHERE content LIKE '%tokenA%'")
    info = eng.health(CTX, verify=True)["index"]
    if info.get("consistent") is False:
        assert info["state"] != str(IndexHealth.HEALTHY), \
            "health reported HEALTHY and consistent=False simultaneously"


def test_rebuild_index_restores_health(eng: Engine) -> None:
    s = eng.add_source(CTX, uri="mem://s", trust=0.9)
    eng.assert_fact(CTX, subject="A", predicate="p", object="tok", source=s.id)
    eng.lexical_index.mark_degraded()
    assert eng.lexical_index.health() is IndexHealth.DEGRADED
    eng.rebuild_index()
    assert eng.lexical_index.health() is IndexHealth.HEALTHY
    hits = eng.search(CTX, text="tok", limit=10)
    assert hits and hits[0]["retrieval_method"].startswith("fts5")


def test_rebuild_projection_restores_health(eng: Engine) -> None:
    """LT-07: rebuild_projection must leave the index usable, not stuck on the scan."""
    s = eng.add_source(CTX, uri="mem://s", trust=0.9)
    eng.assert_fact(CTX, subject="A", predicate="p", object="tok", source=s.id)
    eng.lexical_index.mark_degraded()
    eng.rebuild_projection()
    assert eng.lexical_index.health() is IndexHealth.HEALTHY
    assert eng.provenance_index.health() is IndexHealth.HEALTHY
    hits = eng.search(CTX, text="tok", limit=10)
    assert hits and hits[0]["retrieval_method"].startswith("fts5")


def test_empty_text_object_does_not_force_rebuild_every_open(tmp_path) -> None:
    """B-06: an object with no searchable text must not defeat ensure_built's fast path."""
    path = tmp_path / "e.db"
    e1 = Engine(SQLiteStore(path), clock=ManualClock())
    s = e1.add_source(CTX, uri="mem://s", trust=0.9)
    e1.assert_fact(CTX, subject="A", predicate="p", object="findme", source=s.id)
    e1.observe(CTX, text="")  # empty searchable text
    e1.close()

    # Reopen and assert the index was NOT rebuilt (it is already consistent).
    import epistemos.index.fts as fts_mod
    calls = {"n": 0}
    orig = fts_mod.SqliteFtsIndex.rebuild

    def counting_rebuild(self, store=None):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return orig(self, store)

    fts_mod.SqliteFtsIndex.rebuild = counting_rebuild  # type: ignore[method-assign]
    try:
        e2 = Engine(SQLiteStore(path), clock=ManualClock())
        assert calls["n"] == 0, "ensure_built rebuilt an already-consistent index"
        assert e2.search(CTX, text="findme", limit=10)
        e2.close()
    finally:
        fts_mod.SqliteFtsIndex.rebuild = orig  # type: ignore[method-assign]


def test_scan_query_terms_are_bounded(eng: Engine) -> None:
    """B-03: the scan fallback must cap query terms like the FTS path, not accept a huge OR."""
    from epistemos.index.text import MAX_QUERY_TERMS

    s = eng.add_source(CTX, uri="mem://s", trust=0.9)
    eng.assert_fact(CTX, subject="A", predicate="p", object="findme", source=s.id)
    eng.lexical_index.mark_degraded()  # force the scan
    huge = " ".join(f"term{i}" for i in range(5000))
    # capture how many terms the scan actually scored via the tokenizer bound
    from epistemos.retrieval import LegacyScanRetriever
    scanner = LegacyScanRetriever(tokenizer=eng.tokenizer)
    # the retriever must not consider more than MAX_QUERY_TERMS distinct query terms
    res = eng.search(CTX, text=huge + " findme", limit=10)
    assert isinstance(res, list)
    # direct check: the bound is applied
    toks = eng.tokenizer.tokens(huge)
    assert len(set(toks)) > MAX_QUERY_TERMS
    # after the fix, the scan caps internally; assert via a helper the retriever exposes
    assert scanner._query_terms(huge) is not None
    assert len(scanner._query_terms(huge)) <= MAX_QUERY_TERMS
