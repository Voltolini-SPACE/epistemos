"""Adversarial retrieval battery (E-2 §12) and the scan/index parity constraint E-2 uncovered.

Two things live here. First, the degenerate and hostile queries a retriever meets in production:
empty input, punctuation, stuffing, duplicates, extreme lengths. Second, the invariant that killed
E-2's tokenizer adoption — the legacy scan and the FTS index must answer the same question the
same way, and a tokenizer whose transformations SQLite cannot reproduce silently breaks that.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from epistemos import Engine, Principal
from epistemos.storage import MemoryStore

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks"))

pytestmark = pytest.mark.security

CTX = Principal(tenant="acme", agent="a", namespace="kb")


def _engine(tmp_path=None, tokenizer="ascii"):
    return Engine.open(str(tmp_path / "kb.epistemos") if tmp_path else None, tokenizer=tokenizer)


# -- degenerate input --------------------------------------------------------


@pytest.mark.parametrize("query", ["", "   ", "\t\n", "...", "!!!", "---", "()[]{}", "@@@ ###"])
def test_a_degenerate_query_returns_nothing_not_everything(query):
    """A query that tokenises to nothing is a text search that matched no term, not the absence
    of a text constraint. Confusing the two turns bad input into an unfiltered dump."""
    eng = _engine()
    for i in range(5):
        eng.ingest_document(CTX, title=f"d{i}", text="The retention window is ninety days.")
    assert eng.search(CTX, text=query, limit=50) == []
    eng.close()


def test_a_query_with_no_match_returns_nothing():
    eng = _engine()
    eng.ingest_document(CTX, title="d", text="The retention window is ninety days.")
    assert eng.search(CTX, text="zzzznosuchterm", limit=50) == []
    eng.close()


def test_metadata_only_search_still_works():
    """The fail-closed rule must not break the legitimate case it sits next to: `text=None` means
    no text constraint, and a structural query is allowed to return everything in scope."""
    eng = _engine()
    for i in range(3):
        eng.ingest_document(CTX, title=f"d{i}", text="content")
    assert len(eng.search(CTX, limit=50)) == 3
    eng.close()


# -- stuffing and length -----------------------------------------------------


def test_keyword_stuffing_loses_to_a_real_statement():
    eng = _engine()
    eng.ingest_document(CTX, title="real",
                        text="For the payments scope, the retention window is ninety days.\n")
    eng.ingest_document(CTX, title="stuffed",
                        text=("retention window " * 40) + "\n")
    top = eng.search(CTX, text="retention window payments", limit=5)[0]
    assert eng.get(CTX, top["id"]).title == "real"
    eng.close()


def test_an_enormous_document_does_not_dominate_by_size_alone():
    """Length normalisation must cut both ways: a huge document that mentions the terms in
    passing should not beat a short one that is about them."""
    eng = _engine()
    eng.ingest_document(CTX, title="focused", text="The retention window is ninety days.\n")
    eng.ingest_document(CTX, title="huge",
                        text=("Unrelated prose about many other topics. " * 400)
                             + "retention window\n")
    top = eng.search(CTX, text="retention window", limit=5)[0]
    assert eng.get(CTX, top["id"]).title == "focused"
    eng.close()


def test_a_one_word_document_is_retrievable():
    eng = _engine()
    eng.ingest_document(CTX, title="tiny", text="retention")
    assert len(eng.search(CTX, text="retention", limit=5)) == 1
    eng.close()


def test_exact_duplicates_both_surface_and_neither_is_dropped():
    """Two identical documents are two pieces of evidence. Silently collapsing them would destroy
    the very thing an evidence-first system is for."""
    eng = _engine()
    body = "The retention window is ninety days.\n"
    a = eng.ingest_document(CTX, title="copy-a", text=body)
    b = eng.ingest_document(CTX, title="copy-b", text=body)
    ids = {r["id"] for r in eng.search(CTX, text="retention window", limit=10)}
    assert {a.id, b.id} <= ids
    eng.close()


def test_near_duplicates_are_both_returned_and_ranked_stably():
    eng = _engine()
    eng.ingest_document(CTX, title="a", text="The retention window is ninety days.\n")
    eng.ingest_document(CTX, title="b", text="The retention window is thirty days.\n")
    runs = {tuple(r["id"] for r in eng.search(CTX, text="retention window", limit=10))
            for _ in range(5)}
    assert len(runs) == 1
    assert len(next(iter(runs))) == 2
    eng.close()


def test_conflicting_documents_both_surface():
    """Retrieval finds candidates; it must never resolve a conflict on its own."""
    eng = _engine()
    eng.ingest_document(CTX, title="a", text="For scope X the retention window is five years.\n")
    eng.ingest_document(CTX, title="b", text="For scope X the retention window is seven years.\n")
    titles = {eng.get(CTX, r["id"]).title
              for r in eng.search(CTX, text="scope X retention window", limit=10)}
    assert {"a", "b"} <= titles
    eng.close()


# -- unicode and orthography -------------------------------------------------


@pytest.mark.parametrize("text", [
    "The retenção window is ninety days.",
    "Der Rückhalte-Zeitraum ist neunzig Tage.",
    "保持期間は九十日です。retention",
    "retention​window",          # zero-width space
    "reténtion window",     # combining acute
])
def test_unicode_input_is_indexed_without_crashing(text):
    """Hostile or merely unusual encodings must be inert data, never a parser exploit."""
    eng = _engine()
    doc = eng.ingest_document(CTX, title="u", text=text)
    assert doc.id
    eng.search(CTX, text="retention", limit=5)
    eng.close()


def test_a_hyphenated_identifier_is_retrievable_by_its_parts():
    eng = _engine()
    eng.ingest_document(CTX, title="d", text="The payments-api handles authorisation.\n")
    assert eng.search(CTX, text="payments", limit=5)
    assert eng.search(CTX, text="api", limit=5)
    eng.close()


# -- scan / index parity: the constraint that decided E-2 --------------------


def test_shipped_tokenizer_gives_the_same_answer_on_both_paths(tmp_path):
    """The legacy scan is the correctness reference; the FTS index is an optimisation. If they
    disagree, one of them is lying about what the corpus contains."""
    body = "Several audits were recorded. The retention window is ninety days.\n"
    queries = ["audits", "audit", "retention", "recorded", "ninety"]

    indexed = _engine(tmp_path)
    indexed.ingest_document(CTX, title="d", text=body)
    assert indexed.lexical_index is not None, "this test is meaningless without the FTS index"
    idx_counts = {q: len(indexed.search(CTX, text=q, limit=10)) for q in queries}
    indexed.lexical_index = None          # same store, same data, scan path
    scan_counts = {q: len(indexed.search(CTX, text=q, limit=10)) for q in queries}
    indexed.close()

    assert idx_counts == scan_counts, (
        f"scan/index parity broken: indexed={idx_counts} scan={scan_counts}")


def test_a_tokenizer_sqlite_cannot_reproduce_breaks_parity(tmp_path):
    """Documents the E-2 finding as an executable fact, so nobody re-adopts it by accident.

    A Python tokenizer that normalises plurals while declaring `fts_tokenize="ascii"` makes the
    FTS table store `audits` while the query asks for `audit`. The FTS5 `tokenize=` option is
    fixed at CREATE and SQLite ships no plural-normalising tokenizer, so the transformation
    cannot be pushed down. Adopting it would need the *indexed content* to be pre-normalised —
    a migration, not a patch. See docs/benchmarks/E2_RETRIEVAL.md.
    """
    from e2_tokenizers import PluralNormalising

    body = "Several audits were recorded.\n"
    eng = _engine(tmp_path, tokenizer=PluralNormalising())
    eng.ingest_document(CTX, title="d", text=body)
    indexed = len(eng.search(CTX, text="audits", limit=10))
    eng.lexical_index = None
    scan = len(eng.search(CTX, text="audits", limit=10))
    eng.close()

    assert (indexed, scan) == (0, 1), (
        "E-2's parity finding no longer reproduces — re-run the matrix before changing the "
        f"deferral decision (indexed={indexed}, scan={scan})")


# -- receipts under adversarial input ----------------------------------------


def test_a_receipt_records_which_lexical_variant_produced_it():
    """E-2 measured the same scorer returning very different rankings under different tokenizers.
    A receipt that named only the scorer would be unreplayable."""
    from e2_tokenizers import PluralNormalising

    seals = {}
    for tok in ("ascii", PluralNormalising()):
        eng = _engine(tokenizer=tok)
        eng.ingest_document(CTX, title="d", text="The retention window is ninety days.\n")
        _res, receipt = eng.search_sealed(CTX, text="retention")
        assert receipt.verify()
        seals[receipt.lexical_variant] = receipt.receipt_hash
        eng.close()

    assert set(seals) == {"ascii", "e2-plurals"}
    assert len(set(seals.values())) == 2, "different lexical variants must seal differently"


def test_a_degenerate_query_still_produces_a_verifiable_receipt():
    eng = _engine()
    eng.ingest_document(CTX, title="d", text="content")
    results, receipt = eng.search_sealed(CTX, text="   ")
    assert results == []
    assert receipt.verify()
    assert receipt.execution["result_count"] == 0
    eng.close()


def test_cross_tenant_stuffing_cannot_pull_another_tenants_document():
    store = MemoryStore()
    eng = Engine(store)
    a = Principal(tenant="acme", agent="x", namespace="kb")
    b = Principal(tenant="globex", agent="x", namespace="kb")
    secret = eng.ingest_document(b, title="secret", text=("retention window " * 50))
    eng.ingest_document(a, title="mine", text="The retention window is ninety days.\n")

    ids = {r["id"] for r in eng.search(a, text="retention window", limit=50)}
    assert secret.id not in ids
    eng.close()
