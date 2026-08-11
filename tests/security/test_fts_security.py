"""FTS / index security battery (EPISTEMOS-02 ETAPA 16).

The safe normalizer turns user text into quoted literal tokens, so no FTS5/SQL operator in the
query can change behavior; tenant/namespace are enforced at the SQL boundary; and the index is a
projection (a malicious document is inert data, searchable but never executed).
"""

from __future__ import annotations

import sqlite3

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.index.text import MAX_QUERY_TERMS, fts_match_query
from epistemos.storage import SQLiteStore

pytestmark = pytest.mark.security


@pytest.fixture
def eng(tmp_path) -> Engine:
    e = Engine(SQLiteStore(tmp_path / "sec.db"), clock=ManualClock())
    return e


ATTACK_QUERIES = [
    '"; DROP TABLE fts_idx; --',
    "MATCH OR NEAR(a b, 5)",
    "alice AND NOT bob",
    "foo*bar prefix*",
    'unbalanced "quote here',
    "(((((deep)))))",
    "tenant:globex namespace:secret",
    "a" * 5000,  # very long single token
    "α β γ δ ε ζ",  # non-ascii (confusables / unicode)
    "col:val AND x:y OR z:*",
]


@pytest.mark.parametrize("q", ATTACK_QUERIES)
def test_hostile_query_never_errors_and_never_executes(eng: Engine, q: str) -> None:
    ctx = Principal(tenant="acme", agent="a", namespace="hr")
    eng.add_source(ctx, uri="mem://s", trust=0.9)
    eng.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme")
    # must not raise, must not drop/alter the index, must return a list
    res = eng.search(ctx, text=q, limit=10)
    assert isinstance(res, list)
    # index tables intact + consistent after the hostile query
    assert eng.verify_index_consistency()
    assert eng.health(ctx)["index"]["state"] == "INDEX_HEALTHY"


def test_query_term_cap_bounds_explosion() -> None:
    match = fts_match_query(" ".join(f"tok{i}" for i in range(10_000)))
    assert match is not None
    # capped number of OR clauses (each term is a quoted literal)
    assert match.count(" OR ") + 1 <= MAX_QUERY_TERMS


def test_fts_operators_are_literal_tokens(eng: Engine) -> None:
    ctx = Principal(tenant="acme", agent="a", namespace="hr")
    # a fact whose text literally contains FTS/SQL operators
    poison = "OR AND NOT NEAR DROP TABLE objects MATCH"
    f = eng.assert_fact(ctx, subject=poison, predicate="p", object="v")
    # searching those words as literals finds the fact; nothing is executed
    res = eng.search(ctx, text="DROP TABLE", limit=5)
    assert any(r["id"] == f.id for r in res)
    assert eng.verify_index_consistency()


def test_tenant_and_namespace_cannot_be_bypassed_via_query(eng: Engine) -> None:
    acme = Principal(tenant="acme", agent="a", namespace="hr")
    globex = Principal(tenant="globex", agent="b", namespace="hr")
    other_ns = Principal(tenant="acme", agent="a", namespace="finance")
    eng.assert_fact(acme, subject="Secret", predicate="p", object="acmevalue")
    # FTS column-filter-looking query cannot escape the tenant/namespace WHERE clause
    for hostile in ("Secret", "tenant:acme Secret", '"acme" OR Secret', "acmevalue"):
        assert eng.search(globex, text=hostile) == []
        assert eng.search(other_ns, text=hostile) == []


def test_import_rebuilds_index_no_injectable_index_metadata() -> None:
    # The export format carries the ledger, not an index; import replays events and rebuilds the
    # index from authoritative state, so there is no index metadata to poison.
    ctx = Principal(tenant="acme", agent="a", namespace="hr")
    from epistemos.storage import MemoryStore
    src = Engine(MemoryStore())
    src.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme")
    dump = src.export()
    assert "index" not in dump and "fts" not in dump

    import tempfile
    dst = Engine(SQLiteStore(tempfile.mkdtemp() + "/imp.db"))
    dst.import_events(dump)
    dst.rebuild_index()
    assert dst.verify_index_consistency()
    assert dst.search(ctx, text="Alice Acme")


def test_index_corruption_detected_by_verify(eng: Engine) -> None:
    ctx = Principal(tenant="acme", agent="a", namespace="hr")
    eng.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme")
    # simulate stale-index poisoning / corruption: delete an index row out-of-band
    with eng.lexical_index._lock:
        eng.lexical_index._conn.execute("DELETE FROM fts_idx")
        eng.lexical_index._conn.execute("DELETE FROM fts_map")
    assert eng.verify_index_consistency() is False  # drift detected
    assert eng.health(ctx)["index"]["state"] == "INDEX_DEGRADED"  # verify marked it
    # search still correct via fallback; rebuild restores health
    assert eng.search(ctx, text="Alice")
    eng.rebuild_index()
    assert eng.verify_index_consistency()
    _ = sqlite3  # imported for clarity of intent
