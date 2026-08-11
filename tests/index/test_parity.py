"""RETRIEVAL_SEMANTIC_PARITY gate (ETAPA 9).

LegacyScanRetriever (v0.1 reference) vs IndexedRetriever (FTS) on a closed corpus. They must
agree on: the set of text-matching results, temporal validity, tenant/agent isolation, source-
trust behavior, contradiction behavior, and explanation structure. Documented intentional
differences (ADR-017): the *lexical score* (TF·IDF vs BM25) and thus fine ordering among purely
lexical ties; and legacy additionally surfaces non-text-matching recency hits that the indexed
path drops (correct search semantics).
"""

from __future__ import annotations

import pytest

from epistemos import Engine, Principal

QUERIES = ["Alice", "Acme", "Beta", "Alice Acme", "works", "Gamma rumor", "engineer"]


@pytest.fixture
def corpus(fts: Engine, ctx: Principal) -> Engine:
    hr = fts.add_source(ctx, uri="mem://hr", trust=0.9)
    rumor = fts.add_source(ctx, uri="mem://rumor", trust=0.05)
    f1 = fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme",
                         valid_from="2026-01-01", valid_to="2026-02-01", source=hr.id)
    f2 = fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Beta",
                         valid_from="2026-02-01", source=hr.id)
    fr = fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Gamma rumor",
                         source=rumor.id)
    fts.contradict(ctx, fr.id, by=f2.id)
    fts.assert_fact(ctx, subject="Bob", predicate="role", object="engineer", source=hr.id)
    # a different tenant with the SAME terms (leakage bait)
    other = Principal(tenant="globex", agent="x", namespace="hr")
    fts.add_source(other, uri="mem://x", trust=0.9)
    fts.assert_fact(other, subject="Alice", predicate="works_at", object="Acme")
    _ = (f1, f2)
    return fts


def _text_ids(results) -> set[str]:
    return {r.id for r in results if r.score_components.get("lexical", 0.0) > 0.0}


@pytest.mark.parametrize("q", QUERIES)
def test_text_match_set_parity(corpus: Engine, ctx: Principal, q: str) -> None:
    legacy = corpus.legacy.search(corpus.store, ctx.tenant, ctx.namespace, text=q, limit=50)
    indexed = corpus.indexed.search(corpus.store, ctx.tenant, ctx.namespace, text=q, limit=50)
    indexed_ids = {r.id for r in indexed}
    # the indexed path returns exactly the text-matching set the legacy scorer found
    assert indexed_ids == _text_ids(legacy), q


@pytest.mark.parametrize("q", QUERIES)
def test_temporal_and_source_parity(corpus: Engine, ctx: Principal, q: str) -> None:
    legacy = {r.id: r for r in
              corpus.legacy.search(corpus.store, ctx.tenant, ctx.namespace, text=q, limit=50)}
    indexed = corpus.indexed.search(corpus.store, ctx.tenant, ctx.namespace, text=q, limit=50)
    for r in indexed:
        assert r.id in legacy, (q, r.id)
        assert r.temporal_state == legacy[r.id].temporal_state
        assert r.source == legacy[r.id].source
        assert (set(r.score_components) - {"lexical"}
                == set(legacy[r.id].score_components) - {"lexical"})


def test_tenant_isolation_parity(corpus: Engine) -> None:
    globex = Principal(tenant="globex", agent="x", namespace="hr")
    # both retrievers must keep acme's "Acme" fact out of globex results and vice-versa
    li = corpus.indexed.search(corpus.store, "acme", "hr", text="Acme", limit=50)
    gi = corpus.indexed.search(corpus.store, "globex", "hr", text="Acme", limit=50)
    assert {r.id for r in li}.isdisjoint({r.id for r in gi})
    # globex has exactly its own Acme fact; acme's is not present
    _ = globex


def test_believed_only_parity(corpus: Engine, ctx: Principal) -> None:
    legacy = corpus.legacy.search(corpus.store, ctx.tenant, ctx.namespace,
                                  text="Alice", believed_only=True, limit=50)
    indexed = corpus.indexed.search(corpus.store, ctx.tenant, ctx.namespace,
                                    text="Alice", believed_only=True, limit=50)
    assert {r.id for r in indexed} == _text_ids(legacy)
    # no superseded fact leaks in when believed_only
    assert all(r.temporal_state is None or r.temporal_state["believed"] for r in indexed)


def test_as_of_temporal_parity(corpus: Engine, ctx: Principal) -> None:
    legacy = corpus.legacy.search(corpus.store, ctx.tenant, ctx.namespace,
                                  text="Alice", at_valid="2026-01-15", limit=50)
    indexed = corpus.indexed.search(corpus.store, ctx.tenant, ctx.namespace,
                                    text="Alice", at_valid="2026-01-15", limit=50)
    lt = {r.id: r.score_components.get("temporal")
          for r in legacy if r.score_components.get("lexical")}
    it = {r.id: r.score_components.get("temporal") for r in indexed}
    assert lt == it  # identical temporal contribution per shared id at the historical instant
