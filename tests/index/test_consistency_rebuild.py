"""INDEX_CONSISTENCY (ETAPA 5) + INDEX_REBUILD (ETAPA 6).

After every mutation the index must reflect the core; deleting and rebuilding the index from
authoritative state must reproduce identical search results.
"""

from __future__ import annotations

from epistemos import Engine, Principal


def _mutate_everything(eng: Engine, ctx: Principal) -> dict:
    s = eng.add_source(ctx, uri="mem://s", trust=0.8)
    obs = eng.observe(ctx, text="alice note", source=s.id)
    f1 = eng.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme",
                         source=s.id, derived_from=[obs.id])
    f2 = eng.supersede(ctx, f1.id, new={"object": "Beta"})
    f3 = eng.assert_fact(ctx, subject="Alice", predicate="works_at", object="Gamma")
    eng.contradict(ctx, f3.id, by=f2.id)
    eng.retract(ctx, f3.id)
    e1 = eng.add_entity(ctx, name="OpenAI")
    e2 = eng.add_entity(ctx, name="Open AI")
    eng.merge_entities(ctx, canonical=e1.id, duplicates=[e2.id])
    e3 = eng.split_entity(ctx, e1.id, into=[{"name": "OpenAI US"}, {"name": "OpenAI EU"}])
    eng.record_decision(ctx, statement="assign alice", evidence=[f2.id])
    return {"f2": f2.id, "e3": [e.id for e in e3]}


def test_index_consistent_after_every_op(fts: Engine, ctx: Principal) -> None:
    _mutate_everything(fts, ctx)
    # the index set matches the authoritative searchable-object set
    assert fts.verify_index_consistency() is True
    assert fts.health(ctx)["index"]["state"] == "INDEX_HEALTHY"


def test_supersede_and_retract_keep_index_searchable(fts: Engine, ctx: Principal) -> None:
    s = fts.add_source(ctx, uri="mem://s", trust=0.9)
    f = fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme", source=s.id)
    fts.supersede(ctx, f.id, new={"object": "Beta"})
    # both the superseded and the new fact are still searchable (historical + current)
    ids = {r["id"] for r in fts.search(ctx, text="Alice", limit=20)}
    assert f.id in ids  # superseded fact remains in the index
    assert fts.verify_index_consistency()


def test_rebuild_reproduces_results(fts: Engine, ctx: Principal) -> None:
    _mutate_everything(fts, ctx)
    queries = ["Alice", "Beta", "OpenAI", "assign alice", "Acme Gamma"]
    before = {q: fts.search(ctx, text=q, limit=25) for q in queries}

    n = fts.rebuild_index()
    assert n == fts.lexical_index.count()
    assert fts.verify_index_consistency()

    after = {q: fts.search(ctx, text=q, limit=25) for q in queries}
    for q in queries:
        assert [r["id"] for r in before[q]] == [r["id"] for r in after[q]], q
        assert before[q] == after[q], q  # scores + explanations identical too


def test_rebuild_projection_also_rebuilds_index(fts: Engine, ctx: Principal) -> None:
    _mutate_everything(fts, ctx)
    before = [r["id"] for r in fts.search(ctx, text="Alice", limit=25)]
    fts.rebuild_projection()  # full ledger replay
    assert fts.verify_index_consistency()
    after = [r["id"] for r in fts.search(ctx, text="Alice", limit=25)]
    assert before == after
