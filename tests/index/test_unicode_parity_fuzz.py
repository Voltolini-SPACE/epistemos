"""Fuzz the scan/index parity invariant for the unicode tokenizer (ADR-023).

The design claim is that routing tokenization through SQLite makes the python scan and the FTS
index agree BY CONSTRUCTION. This test tries to break that on random multilingual text: for many
random (corpus, query) pairs, the legacy scan and the indexed retriever must return the identical
result set. A single divergence fails the gate.
"""

from __future__ import annotations

import random

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.storage import SQLiteStore

POOLS = [
    "abcdefghijklmnopqrstuvwxyz0123456789",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "áàâãäéèêëíìîïóòôõöúùûüçñ",
    "ØøÅåÆæŒœßłŁðÞ",
    "αβγδεζηθικλμνξοπ",
    "абвгдеёжзиклмноп",
    "日本語中文漢字",
    "한국어테스트트",
    " -_.,;:()[]/@#",
]


def _rand(rng: random.Random, maxlen: int = 24) -> str:
    return "".join(rng.choice(rng.choice(POOLS)) for _ in range(rng.randint(1, maxlen)))


@pytest.fixture
def ctx() -> Principal:
    return Principal(tenant="acme", agent="claude", namespace="hr")


def test_unicode_scan_index_parity_fuzz(tmp_path, ctx: Principal) -> None:
    rng = random.Random(20260811)
    eng = Engine(SQLiteStore(tmp_path / "fuzz.db"), clock=ManualClock(), tokenizer="unicode")
    src = eng.add_source(ctx, uri="mem://s", trust=0.8)

    contents = [_rand(rng) for _ in range(120)]
    for i, c in enumerate(contents):
        eng.assert_fact(ctx, subject=f"S{i}", predicate="about", object=c, source=src.id)

    # queries: some drawn from the corpus (guaranteeing hits), some random (often empty)
    queries = [rng.choice(contents) for _ in range(60)] + [_rand(rng, 12) for _ in range(60)]
    divergences = []
    for q in queries:
        legacy = {r.id for r in eng.legacy.search(eng.store, ctx.tenant, ctx.namespace,
                                                  text=q, limit=200)}
        indexed = {r.id for r in eng.indexed.search(eng.store, ctx.tenant, ctx.namespace,
                                                    text=q, limit=200)}
        if legacy != indexed:
            divergences.append((q, sorted(legacy - indexed), sorted(indexed - legacy)))
    assert not divergences, f"{len(divergences)} scan/index divergences, e.g. {divergences[:3]}"
    eng.close()
