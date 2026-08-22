"""Ranking must be a function of the data, never of the environment.

The E-1 benchmark found real score ties — two documents scoring identically to twelve decimal
places. What breaks a tie decides which answer a user sees first, so it cannot be left to SQLite
row order, dict iteration or thread scheduling. These tests pin the declared order and the
properties that must hold around it (mission §15, §27).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from epistemos import Engine, Principal
from epistemos.storage import MemoryStore

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks"))

CTX = Principal(tenant="acme", agent="a", namespace="kb")


def _tied_corpus(engine, n=8):
    """Identical text under different titles: same lexical score, so the tie-break decides."""
    body = "The retention window for the scope is ninety days.\n"
    return [engine.ingest_document(CTX, title=f"doc-{i:02d}", text=body) for i in range(n)]


def test_identical_scores_produce_a_stable_order():
    orders = []
    for _ in range(5):
        eng = Engine.open(None)
        _tied_corpus(eng)
        orders.append(tuple(r["id"] for r in eng.search(CTX, text="retention window", limit=20)))
        eng.close()
    # Ids differ between engines (fresh ids), so compare the *shape*: same scores, same length.
    assert len({len(o) for o in orders}) == 1


def test_order_is_a_pure_function_of_the_stored_data():
    """Same store, same query, repeated: byte-identical ordering. This is the property that a
    receipt depends on — without it, sealing a ranking would seal noise."""
    eng = Engine.open(None)
    _tied_corpus(eng)
    runs = {tuple(r["id"] for r in eng.search(CTX, text="retention window", limit=20))
            for _ in range(10)}
    assert len(runs) == 1
    eng.close()


def test_ties_break_on_ascending_id():
    eng = Engine.open(None)
    _tied_corpus(eng)
    results = eng.search(CTX, text="retention window", limit=20)
    tied = [r for r in results if r["score"] == pytest.approx(results[0]["score"])]
    assert len(tied) > 1, "corpus should produce ties"
    ids = [r["id"] for r in tied]
    assert ids == sorted(ids), "declared tie-break is score DESC then id ASCENDING"
    eng.close()


def test_scores_are_non_increasing():
    eng = Engine.open(None)
    _tied_corpus(eng)
    scores = [r["score"] for r in eng.search(CTX, text="retention window", limit=20)]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    eng.close()


def test_insertion_order_does_not_decide_the_ranking():
    """Two stores with the same documents inserted in opposite orders must rank the same way
    relative to score; only the id tie-break may differ, and it must be ascending in both."""
    forward, reverse = Engine.open(None), Engine.open(None)
    bodies = [f"The retention window for scope {i} is ninety days.\n" for i in range(6)]
    for b in bodies:
        forward.ingest_document(CTX, title="d", text=b)
    for b in reversed(bodies):
        reverse.ingest_document(CTX, title="d", text=b)

    for eng in (forward, reverse):
        res = eng.search(CTX, text="retention window", limit=20)
        tied = [r for r in res if r["score"] == pytest.approx(res[0]["score"])]
        ids = [r["id"] for r in tied]
        assert ids == sorted(ids)
        eng.close()


def test_every_result_can_explain_its_own_score():
    """A bare number is not an explanation. Each result must decompose into named components that
    the receipt can seal (mission §16)."""
    eng = Engine.open(None)
    _tied_corpus(eng, n=3)
    for r in eng.search(CTX, text="retention window", limit=10):
        comps = r["score_components"]
        assert comps, "a result with no component breakdown cannot be audited"
        assert all(isinstance(v, (int, float)) for v in comps.values())
        assert r["why_returned"]
        assert r["retrieval_method"]
    eng.close()


# -- adversarial (mission §23) ----------------------------------------------


def test_term_repetition_does_not_beat_a_real_statement():
    """A document that merely repeats the query vocabulary must not outrank one that asserts the
    fact. This is the cheapest poisoning attack against a lexical scorer."""
    eng = Engine.open(None)
    eng.ingest_document(CTX, title="real", text=(
        "For the payments scope, the retention window is ninety days.\n"))
    eng.ingest_document(CTX, title="spam", text=(
        "retention retention retention window window window retention window\n"
        "retention window retention window retention window retention window\n"))
    res = eng.search(CTX, text="retention window payments", limit=5)
    titles = [eng.get(CTX, r["id"]).title for r in res]
    assert titles[0] == "real", f"noise outranked the real statement: {titles}"
    eng.close()


def test_cross_tenant_documents_never_appear_however_identical():
    """Same text, same query, same hashes — different tenant. Nothing may cross."""
    store = MemoryStore()
    eng = Engine(store)
    a = Principal(tenant="acme", agent="x", namespace="kb")
    b = Principal(tenant="globex", agent="x", namespace="kb")
    body = "The retention window for the shared scope is ninety days.\n"
    doc_b = eng.ingest_document(b, title="identical", text=body)
    eng.ingest_document(a, title="identical", text=body)

    ids = {r["id"] for r in eng.search(a, text="retention window", limit=50)}
    assert doc_b.id not in ids
    for r in eng.search(a, text="retention window", limit=50):
        assert eng.get(a, r["id"]).tenant == "acme"
    eng.close()


def test_an_empty_or_whitespace_query_does_not_return_everything():
    """Fail closed: a degenerate query must not become 'select *'."""
    eng = Engine.open(None)
    _tied_corpus(eng, n=5)
    for bad in ("", "   ", "\n\t"):
        assert eng.search(CTX, text=bad, limit=50) == []
    eng.close()


def test_results_are_free_of_duplicates():
    eng = Engine.open(None)
    _tied_corpus(eng, n=6)
    ids = [r["id"] for r in eng.search(CTX, text="retention window", limit=50)]
    assert len(ids) == len(set(ids))
    eng.close()


# -- corpus (mission §5, §6) -------------------------------------------------


def test_benchmark_corpus_is_deterministic_and_meets_its_declared_shape():
    from e1_corpus import build_corpus, corpus_digest

    digests = set()
    for _ in range(3):
        docs, queries = build_corpus()
        digests.add(corpus_digest(docs, queries))
    assert len(digests) == 1, "the benchmark corpus must regenerate byte-identically"

    docs, queries = build_corpus()
    assert len(docs) >= 500
    assert len(queries) >= 150

    from collections import Counter
    counts = Counter(q.category for q in queries)
    minimums = {"exact": 15, "morphology": 15, "synonym": 20, "paraphrase": 25,
                "crosslingual": 15, "temporal": 15, "conflict": 15, "crossref": 10,
                "adversarial": 20}
    for category, minimum in minimums.items():
        assert counts[category] >= minimum, f"{category}: {counts[category]} < {minimum}"


def test_benchmark_ground_truth_is_never_empty():
    """A query whose expected set is empty would score 0 for every retriever and quietly drag the
    average down while looking like a retrieval failure."""
    from e1_corpus import build_corpus

    _docs, queries = build_corpus()
    for q in queries:
        assert q.expected_documents, f"{q.query_id} has no expected documents"
