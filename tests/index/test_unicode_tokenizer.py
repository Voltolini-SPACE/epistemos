"""UNICODE_SEARCH gate (EPISTEMOS-03, ADR-023).

Opt-in unicode-aware, diacritic-folding search. Two properties must hold:

1. **It works.** Non-ASCII content becomes searchable and diacritics fold, which the default
   ascii tokenizer cannot do (measured on v0.2.0: search "Tóquio" -> 0 hits).
2. **Scan and index still agree.** The whole reason tokenization goes through SQLite is that the
   python scan (fallback) and the FTS index must return the same set — otherwise ADR-021's
   just-fixed parity guarantee would break for non-ASCII queries.
"""

from __future__ import annotations

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.index.text import ASCII, UNICODE, fts_match_query
from epistemos.storage import SQLiteStore


@pytest.fixture
def uni(tmp_path) -> Engine:
    return Engine(SQLiteStore(tmp_path / "u.db"), clock=ManualClock(), tokenizer="unicode")


@pytest.fixture
def ctx() -> Principal:
    return Principal(tenant="acme", agent="claude", namespace="hr")


def test_non_ascii_content_is_searchable(uni: Engine, ctx: Principal) -> None:
    src = uni.add_source(ctx, uri="mem://s", trust=0.8)
    uni.assert_fact(ctx, subject="Ana", predicate="mora_em", object="Tóquio", source=src.id)
    hits = uni.search(ctx, text="Tóquio", limit=10)
    assert hits, "unicode mode must find non-ASCII content"
    assert hits[0]["retrieval_method"].startswith("fts5")


def test_diacritics_fold(uni: Engine, ctx: Principal) -> None:
    src = uni.add_source(ctx, uri="mem://s", trust=0.8)
    uni.ingest_document(ctx, title="Relatório", text="contratação de café", source=src.id)
    # query without diacritics finds accented content and vice-versa
    assert uni.search(ctx, text="relatorio", limit=10)
    assert uni.search(ctx, text="CONTRATAÇÃO", limit=10)
    assert uni.search(ctx, text="cafe", limit=10)


def test_scan_and_index_agree_on_non_ascii(uni: Engine, ctx: Principal) -> None:
    """The parity guarantee (ADR-021/023) must hold for unicode queries too."""
    src = uni.add_source(ctx, uri="mem://s", trust=0.8)
    corpus = ["Tóquio", "São Paulo", "café", "CAFÉ", "Ольга", "naïve", "日本語 テスト",
              "número1", "ångström"]
    for i, obj in enumerate(corpus):
        uni.assert_fact(ctx, subject=f"S{i}", predicate="about", object=obj, source=src.id)
    for q in ["toquio", "sao", "cafe", "CAFÉ", "ольга", "naive", "日本語", "número1", "angstrom"]:
        legacy = {r.id for r in uni.legacy.search(uni.store, ctx.tenant, ctx.namespace,
                                                  text=q, limit=50)}
        indexed = {r.id for r in uni.indexed.search(uni.store, ctx.tenant, ctx.namespace,
                                                    text=q, limit=50)}
        assert legacy == indexed, f"scan/index divergence for {q!r}: {legacy} vs {indexed}"


def test_degraded_index_falls_back_identically_unicode(uni: Engine, ctx: Principal) -> None:
    src = uni.add_source(ctx, uri="mem://s", trust=0.8)
    uni.assert_fact(ctx, subject="A", predicate="p", object="Tóquio café", source=src.id)
    healthy = uni.search(ctx, text="cafe", limit=10)
    assert healthy and healthy[0]["retrieval_method"].startswith("fts5")
    uni.lexical_index.mark_degraded()
    degraded = uni.search(ctx, text="cafe", limit=10)
    assert degraded and degraded[0]["retrieval_method"].startswith("scan")
    assert {r["id"] for r in healthy} == {r["id"] for r in degraded}


def test_ascii_content_identical_across_tokenizers(tmp_path, ctx: Principal) -> None:
    """A pure-ASCII corpus must return the same result set in both modes (no ascii regression)."""
    def build(mode: str) -> Engine:
        e = Engine(SQLiteStore(tmp_path / f"{mode}.db"), clock=ManualClock(), tokenizer=mode)
        s = e.add_source(ctx, uri="mem://s", trust=0.8)
        e.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme", source=s.id)
        e.assert_fact(ctx, subject="Bob", predicate="role", object="engineer", source=s.id)
        e.ingest_document(ctx, title="memo", text="quarterly planning review", source=s.id)
        return e
    a = build("ascii")
    u = build("unicode")

    def matched_text(eng: Engine, q: str) -> set[str]:
        # compare by content, not by id: the two engines mint independent uuids
        from epistemos.index.text import object_text
        return {
            object_text(eng.store.get_object(r["id"]))
            for r in eng.search(ctx, text=q, limit=50)
        }

    for q in ["Alice", "Acme", "engineer", "quarterly", "works", "Alice Acme"]:
        assert matched_text(a, q) == matched_text(u, q), \
            f"ascii vs unicode diverged on pure-ASCII query {q!r}"
    a.close()
    u.close()


def test_tokenizer_change_rebuilds_index(tmp_path, ctx: Principal) -> None:
    """Reopening a DB with a different tokenizer rebuilds the index (tokenize= fixed at CREATE)."""
    path = tmp_path / "switch.db"
    e1 = Engine(SQLiteStore(path), clock=ManualClock(), tokenizer="ascii")
    s = e1.add_source(ctx, uri="mem://s", trust=0.8)
    e1.assert_fact(ctx, subject="Ana", predicate="mora_em", object="Tóquio", source=s.id)
    assert e1.search(ctx, text="Tóquio", limit=10) == []  # ascii can't find it
    e1.close()

    e2 = Engine(SQLiteStore(path), clock=ManualClock(), tokenizer="unicode")
    assert e2.verify_index_consistency()
    assert e2.search(ctx, text="toquio", limit=10), "after switch, unicode search must work"
    e2.close()

    # switching back is also clean
    e3 = Engine(SQLiteStore(path), clock=ManualClock(), tokenizer="ascii")
    assert e3.verify_index_consistency()
    e3.close()


def test_unicode_query_injection_is_inert(uni: Engine, ctx: Principal) -> None:
    """FTS/boolean operators inside a unicode query stay data, never syntax."""
    src = uni.add_source(ctx, uri="mem://s", trust=0.8)
    uni.assert_fact(ctx, subject="A", predicate="p", object="café", source=src.id)
    for hostile in ['café OR 1', 'café" OR "x', 'café NEAR bar', 'café*', 'content:café',
                    '"café" AND (', 'café)))', "café';DROP TABLE fts_idx;--"]:
        # must not raise and must not error out of the fallback either
        res = uni.search(ctx, text=hostile, limit=10)
        assert isinstance(res, list)
    # the index survived every hostile query
    assert uni.verify_index_consistency()
    assert uni.search(ctx, text="cafe", limit=10)


def test_fts_match_query_is_safe_under_unicode() -> None:
    # tokens come from SQLite's tokenizer -> no operators survive; quoting is defensive
    q = fts_match_query('café" OR "evil', UNICODE)
    assert q is not None
    assert '"' in q and " OR " in q  # OR is our combiner; inner quotes are escaped literals
    assert fts_match_query("!!!___###", UNICODE) is None  # no terms
    assert fts_match_query("hello world", ASCII) == '"hello" OR "world"'
