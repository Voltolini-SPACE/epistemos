"""PROVENANCE_INDEX gate (EPISTEMOS-03, ADR-022).

The index must be invisible: `explain()` returns byte-identical genealogy whether it is served
by the keyed lookup or by the authoritative ledger scan. These tests pin equality first and
speed second — a faster wrong answer is worse than a slow right one.
"""

from __future__ import annotations

import json

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.index import IndexHealth
from epistemos.index.provenance import ID_SHAPE, id_leaves
from epistemos.provenance import explain as explain_fn
from epistemos.provenance import explain_decision as explain_decision_fn
from epistemos.storage import SQLiteStore


@pytest.fixture
def rich(fts: Engine, ctx: Principal) -> Engine:
    """A corpus exercising every provenance edge: source, derivation, supersession,
    correction, contradiction, confirmation, decision evidence, merge and split."""
    hr = fts.add_source(ctx, uri="mem://hr", trust=0.9)
    rumor = fts.add_source(ctx, uri="mem://rumor", trust=0.05)
    doc = fts.ingest_document(ctx, title="handbook", text="policy text", source=hr.id)
    f1 = fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme",
                         source=hr.id, derived_from=[doc.id])
    f2 = fts.supersede(ctx, f1.id, new=dict(object="Beta"), reason="moved")
    f3 = fts.correct_validity(ctx, f2.id, valid_from="2026-03-01", reason="start date")
    rum = fts.assert_fact(ctx, subject="Alice", predicate="works_at", object="Gamma",
                          source=rumor.id)
    fts.contradict(ctx, rum.id, by=f3.id, note="unverified")
    fts.confirm(ctx, f3.id, source=hr.id, delta_confidence=0.0)
    fts.record_decision(ctx, statement="promote Alice", evidence=[f3.id, doc.id])
    e1 = fts.add_entity(ctx, name="Acme")
    e2 = fts.add_entity(ctx, name="ACME Inc")
    fts.merge_entities(ctx, canonical=e1.id, duplicates=[e2.id])
    fts.split_entity(ctx, e1.id, into=[dict(name="Acme US")])
    fts.remember(ctx, summary="review", facts=[f3.id])
    return fts


def _scan_explain(eng: Engine, ctx: Principal, obj_id: str) -> dict:
    """The authoritative answer: no index at all, mirroring Engine.explain's routing."""
    obj = eng.store.get_object(obj_id)
    if obj is not None and obj.get("kind") == "decision":
        return explain_decision_fn(eng.store, ctx.tenant, ctx.namespace, obj_id, index=None)
    return explain_fn(eng.store, ctx.tenant, ctx.namespace, obj_id, depth=3, index=None)


def _all_ids(eng: Engine, ctx: Principal) -> list[str]:
    return sorted(o["id"] for o in eng.store.objects(ctx.tenant, ctx.namespace))


def test_index_explain_identical_to_scan_for_every_object(rich: Engine, ctx: Principal) -> None:
    """The whole gate: same genealogy, indexed or scanned, for every object in the corpus."""
    ids = _all_ids(rich, ctx)
    assert len(ids) >= 12, "corpus should exercise many object kinds"
    for obj_id in ids:
        indexed = rich.explain(ctx, obj_id)
        scanned = _scan_explain(rich, ctx, obj_id)
        assert json.dumps(indexed, sort_keys=True) == json.dumps(scanned, sort_keys=True), obj_id


def test_index_explain_identical_after_rebuild(rich: Engine, ctx: Principal) -> None:
    before = {i: rich.explain(ctx, i) for i in _all_ids(rich, ctx)}
    rich.rebuild_index()
    assert rich.provenance_index.health() is IndexHealth.HEALTHY
    after = {i: rich.explain(ctx, i) for i in _all_ids(rich, ctx)}
    assert before == after


def test_index_explain_identical_after_projection_rebuild(rich: Engine, ctx: Principal) -> None:
    before = {i: rich.explain(ctx, i) for i in _all_ids(rich, ctx)}
    rich.rebuild_projection()
    assert rich.verify_index_consistency()
    after = {i: rich.explain(ctx, i) for i in _all_ids(rich, ctx)}
    assert before == after


def test_degraded_index_falls_back_to_identical_scan(rich: Engine, ctx: Principal) -> None:
    """A broken provenance index costs latency, never completeness (ADR-019/022)."""
    ids = _all_ids(rich, ctx)
    healthy = {i: rich.explain(ctx, i) for i in ids}
    rich.provenance_index.mark_degraded()
    assert rich.provenance_index.health() is IndexHealth.DEGRADED
    degraded = {i: rich.explain(ctx, i) for i in ids}
    assert healthy == degraded


def test_deleted_index_rows_do_not_truncate_genealogy(rich: Engine, ctx: Principal) -> None:
    """Silent row loss must be caught by verify(), and the answer must stay complete."""
    target = next(o["id"] for o in rich.store.objects(ctx.tenant, ctx.namespace, kind="fact"))
    expected = _scan_explain(rich, ctx, target)
    rich.store._conn.execute("DELETE FROM prov_ref WHERE obj_id = ?", (target,))
    assert rich.verify_index_consistency() is False  # drift detected...
    assert rich.provenance_index.health() is IndexHealth.DEGRADED  # ...and it stops being used
    assert rich.explain(ctx, target) == expected  # so the answer is still complete
    rich.rebuild_index()
    assert rich.verify_index_consistency() is True
    assert rich.explain(ctx, target) == expected


def test_index_never_crosses_tenant_boundary(fts: Engine, ctx: Principal) -> None:
    other = Principal(tenant="globex", agent="x", namespace="hr")
    src = fts.add_source(ctx, uri="mem://a", trust=0.5)
    mine = fts.assert_fact(ctx, subject="A", predicate="p", object="v", source=src.id)
    osrc = fts.add_source(other, uri="mem://b", trust=0.5)
    theirs = fts.assert_fact(other, subject="B", predicate="q", object="w", source=osrc.id)
    # every activity reported for acme's fact belongs to an acme event
    acme_seqs = {r.seq for r in fts.store.read_events()
                 if r.tenant == ctx.tenant and r.namespace == ctx.namespace}
    reported = {a["seq"] for a in fts.explain(ctx, mine.id)["activities"]}
    assert reported and reported <= acme_seqs
    # ...and globex's own events are indexed but unreachable from acme's scope
    assert fts.provenance_index.seqs_for(theirs.id)
    from epistemos.errors import NotFoundError
    with pytest.raises(NotFoundError):
        fts.explain(ctx, theirs.id)


def test_non_id_shaped_object_is_served_by_the_scan(tmp_path) -> None:
    """An imported export may carry hand-authored ids; those bypass the index, not the answer."""
    from epistemos._util import canonical_json, sha256_hex
    from epistemos.ledger import GENESIS_HASH, content_hash

    events = [
        {"op": "source_added", "ts": "2026-01-01T00:00:00Z", "tenant": "t", "namespace": "n",
         "actor": "a", "principal": None,
         "payload": {"id": "src_1", "kind": "source", "tenant": "t", "namespace": "n",
                     "owner": "a", "created_at": "2026-01-01T00:00:00Z", "uri": "mem://s",
                     "source_kind": "note", "trust": 0.7, "confidence": 1.0, "metadata": {}}},
    ]
    prev = GENESIS_HASH
    for seq, ev in enumerate(events, start=1):
        ch = content_hash(ev["op"], ev["payload"])
        header = {"seq": seq, "ts": ev["ts"], "op": ev["op"], "tenant": ev["tenant"],
                  "namespace": ev["namespace"], "actor": ev["actor"],
                  "principal": ev["principal"], "content_hash": ch, "prev_hash": prev}
        entry = sha256_hex(canonical_json(header))
        ev.update(seq=seq, content_hash=ch, prev_hash=prev, entry_hash=entry)
        prev = entry

    eng = Engine(SQLiteStore(tmp_path / "imported.db"), clock=ManualClock())
    eng.import_events({"format": "epistemos-events", "schema_version": 1, "events": events})
    ctx = Principal(tenant="t", agent="a", namespace="n")
    assert eng.provenance_index.is_indexable("src_1") is False
    assert eng.explain(ctx, "src_1")["activities"] == [
        {"seq": 1, "op": "source_added", "ts": "2026-01-01T00:00:00Z", "actor": "a",
         "principal": None, "entry_hash": events[0]["entry_hash"]}
    ]
    eng.close()


def test_id_shape_and_leaf_extraction() -> None:
    assert ID_SHAPE.match("fact_" + "a" * 32)
    assert not ID_SHAPE.match("src_1")
    assert not ID_SHAPE.match("Fact_" + "a" * 32)
    good = "ent_" + "0" * 32
    nested = {"a": [{"b": good}], "c": "plain text", "d": ["src_1", good]}
    assert id_leaves(nested, set()) == {good}
