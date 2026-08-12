"""EPISTEMOS-03 audit: the safe fallback must not change what a query MEANS.

Findings A-03 / A-04.

ADR-019 promises that when the index is not HEALTHY, ``Engine.search`` falls back to "the
correct O(N) LegacyScanRetriever". ADR-017 simultaneously describes the *indexed* path as
having "standard search semantics" and notes that the scan "additionally surfaced non-matching
objects". Both cannot be the reference. Measured on v0.2.0, the same query answered by the two
paths returned different result sets:

* text that matches nothing: indexed -> 0 results, scan -> every object in the namespace;
* a structural filter with a non-fact ``kinds``: indexed -> 0, scan -> the document.

So an index degradation silently converted "find what matches" into "list the namespace,
ranked by recency". These tests pin the two paths to one meaning: **a query constraint
filters**; the retrievers may differ only in lexical scoring and the documented recall bound.
"""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal


@pytest.fixture
def corpus(fts: Engine, ctx: Principal) -> Engine:
    src = fts.add_source(ctx, uri="mem://s", trust=0.8)
    fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme", source=src.id)
    fts.assert_fact(ctx, subject="Bob", predicate="role", object="engineer", source=src.id)
    fts.ingest_document(ctx, title="Alice memo", text="quarterly planning", source=src.id)
    fts.add_entity(ctx, name="Acme", entity_type="org")
    fts.record_decision(ctx, statement="hire Bob")
    return fts


def _ids(results) -> set[str]:
    return {r.id for r in results}


def _both(corpus: Engine, ctx: Principal, **kw):
    legacy = corpus.legacy.search(corpus.store, ctx.tenant, ctx.namespace, **kw)
    indexed = corpus.indexed.search(corpus.store, ctx.tenant, ctx.namespace, **kw)
    return legacy, indexed


def test_no_match_text_returns_nothing_on_both_paths(corpus: Engine, ctx: Principal) -> None:
    """A-03: a query whose terms match nothing must not degrade into 'return everything'."""
    legacy, indexed = _both(corpus, ctx, text="zzzznonexistentqqq", limit=50)
    assert _ids(indexed) == set()
    assert _ids(legacy) == set(), (
        f"scan fallback surfaced {len(legacy)} non-matching objects for a no-match query"
    )


def test_structural_filter_with_non_fact_kind_agrees(corpus: Engine, ctx: Principal) -> None:
    """A-04: a structural constraint filters on both paths; documents have no subject."""
    legacy, indexed = _both(corpus, ctx, subject="Alice", kinds=("document",), limit=50)
    assert _ids(legacy) == _ids(indexed) == set()


def test_structural_filter_selects_only_matching_facts(corpus: Engine, ctx: Principal) -> None:
    legacy, indexed = _both(corpus, ctx, subject="Alice", limit=50)
    assert _ids(legacy) == _ids(indexed)
    assert all(r.obj.get("subject") == "Alice" for r in legacy)
    assert legacy, "a matching structural query must still return its match"


def test_text_match_set_identical_on_both_paths(corpus: Engine, ctx: Principal) -> None:
    for q in ("Alice", "Acme", "engineer", "quarterly", "hire Bob", "Alice Acme"):
        legacy, indexed = _both(corpus, ctx, text=q, limit=50)
        assert _ids(legacy) == _ids(indexed), q


def test_unconstrained_search_still_browses(corpus: Engine, ctx: Principal) -> None:
    """Anti-regression: with no constraints at all, search still lists the scope."""
    legacy, indexed = _both(corpus, ctx, limit=50)
    assert _ids(legacy) == _ids(indexed)
    assert len(legacy) == 6  # 1 source + 2 facts + 1 document + 1 entity + 1 decision


def test_degraded_index_answers_the_same_question(corpus: Engine, ctx: Principal) -> None:
    """The user-visible contract: degrading the index changes speed, not meaning."""
    healthy = corpus.search(ctx, text="Alice", limit=50)
    assert healthy and healthy[0]["retrieval_method"].startswith("fts5")
    corpus.lexical_index.mark_degraded()
    degraded = corpus.search(ctx, text="Alice", limit=50)
    assert degraded and degraded[0]["retrieval_method"].startswith("scan")
    assert {r["id"] for r in healthy} == {r["id"] for r in degraded}

    healthy_none = corpus.search(ctx, text="zzzznonexistentqqq", limit=50)
    degraded_none = corpus.search(ctx, text="zzzznonexistentqqq", limit=50)
    assert healthy_none == degraded_none == []
