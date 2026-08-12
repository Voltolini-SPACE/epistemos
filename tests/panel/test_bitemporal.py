"""Bitemporal / time-travel + provenance regressions (EPISTEMOS-PANEL-HARDENING-01 §11/§12).

The critical gate: ``FUTURE_KNOWLEDGE_LEAK = 0``. A time-travel snapshot at ``at_tx`` must show the
world as it was *believed then* — never a status, evidence link, review or object that only came to
exist later. The panel reconstructs state from the ledger using only events with ``ts <= at_tx``.
"""
from __future__ import annotations

import time

import pytest
from tests.panel.conftest import principal

from epistemos import Engine
from epistemos.api.panel import PanelService
from epistemos.storage import MemoryStore


@pytest.fixture
def eng_panel():
    eng = Engine(MemoryStore())
    yield eng, PanelService(eng)
    eng.close()


def _alice(eng):
    return principal("alice", extra=frozenset({
        "claim.confirm", "claim.dispute", "knowledge.accept", "claim.retract"}))


def _tx(eng, obj_id):
    o = eng.store.get_object(obj_id)
    return o.get("tx_from") or o.get("created_at")


def test_future_knowledge_leak_is_zero(eng_panel):
    eng, panel = eng_panel
    a = _alice(eng)
    claim = eng.create_claim(a, subject="X", predicate="acquired", object="Y")
    time.sleep(0.003)
    midpoint = _tx(eng, eng.create_claim(a, subject="PROBE", predicate="at", object="mid").id)
    time.sleep(0.003)
    # everything below happens AFTER midpoint
    ev = eng.create_evidence(a, title="doc", uri="u")
    eng.attach_evidence(a, evidence_id=ev.id, to_claim=claim.id, relation="supports")
    later_claim = eng.create_claim(a, subject="LATER", predicate="is", object="new")
    eng.retract_claim(a, claim.id, reason="changed mind")

    snap = panel.as_of(a, at_tx=midpoint)
    nodes = {n["id"]: n for n in snap["nodes"]}
    edges = {(e["source"], e["target"]) for e in snap["edges"]}

    # the claim existed at midpoint and was still OPEN then (retraction is in the future)
    assert claim.id in nodes and nodes[claim.id]["status"] == "open"
    # nothing created after midpoint is visible
    assert later_claim.id not in nodes
    assert ev.id not in nodes
    # no evidence edge attached after midpoint
    assert (ev.id, claim.id) not in edges


def test_asof_at_present_reflects_current_state(eng_panel):
    eng, panel = eng_panel
    a = _alice(eng)
    claim = eng.create_claim(a, subject="X", predicate="is", object="Y")
    eng.retract_claim(a, claim.id, reason="x")
    time.sleep(0.003)
    now = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".999999Z"
    snap = panel.as_of(a, at_tx=now)
    nodes = {n["id"]: n for n in snap["nodes"]}
    # viewed at 'now', the retraction IS known
    assert nodes[claim.id]["status"] == "retracted"


def test_asof_before_creation_is_empty(eng_panel):
    eng, panel = eng_panel
    a = _alice(eng)
    eng.create_claim(a, subject="X", predicate="is", object="Y")
    snap = panel.as_of(a, at_tx="2000-01-01T00:00:00Z")  # long before anything existed
    assert snap["nodes"] == [] and snap["edges"] == []


def test_asof_boundary_includes_event_at_exactly_at_tx(eng_panel):
    eng, panel = eng_panel
    a = _alice(eng)
    claim = eng.create_claim(a, subject="X", predicate="is", object="Y")
    at = _tx(eng, claim.id)  # exactly the claim's own tx
    snap = panel.as_of(a, at_tx=at)
    assert claim.id in {n["id"] for n in snap["nodes"]}  # `<=` boundary is inclusive


# -- provenance / explainability: the real causal chain, absence shown honestly ----
def test_claim_detail_exposes_real_provenance_chain(eng_panel):
    eng, panel = eng_panel
    a = _alice(eng)
    src = eng.add_source(a, uri="https://sec.gov/8k", source_kind="filing", trust=0.9)
    claim = eng.create_claim(a, subject="X", predicate="acquired", object="Y", source=src.id)
    ev = eng.create_evidence(a, title="8-K", uri="https://sec.gov/8k")
    eng.attach_evidence(a, evidence_id=ev.id, to_claim=claim.id, relation="supports")
    eng.review_claim(a, claim.id, verdict="confirm", rationale="authentic")
    detail = panel.claim_detail(a, claim.id)
    blob = str(detail)
    # the chain is reachable: evidence + review + derived belief are all present
    assert ev.id in blob
    assert "confirm" in blob
    assert "belief" in detail or "state" in blob or "verdict" in blob


def test_bare_claim_shows_absence_not_fabrication(eng_panel):
    eng, panel = eng_panel
    a = _alice(eng)
    claim = eng.create_claim(a, subject="Lonely", predicate="has", object="nothing")
    detail = panel.claim_detail(a, claim.id)
    # a claim with no evidence/reviews must report emptiness, never invented support
    for key in ("evidence", "reviews"):
        if key in detail:
            assert detail[key] == [] or detail[key] == {} or not detail[key]
