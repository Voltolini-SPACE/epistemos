"""The P0 UI/graph/search leak invariants for the panel boundary (mission §33):

    PRIVATE_UI_LEAK = PRIVATE_GRAPH_LEAK = PRIVATE_SEARCH_LEAK = 0

Every assertion drives the same rule: nothing an unauthorized principal cannot read is ever placed
in a response — not in a listing, a count, a graph node/edge, a search hit, a timeline, or an error.
"""
from __future__ import annotations

import json

import pytest
from tests.panel.conftest import SECRET

from epistemos.errors import NotFoundError


def _dump(x) -> str:
    return json.dumps(x, default=str)


# ---- PRIVATE_UI_LEAK = 0 : counts / listings ----
def test_counts_only_count_authorized_objects(corpus):
    eng, panel, ids = corpus
    a = panel.counts(ids["alice"])
    b = panel.counts(ids["bob"])
    assert a["claims"] > b["claims"]           # alice's private claim is counted only for alice
    assert SECRET not in _dump(b)              # marker never in bob's counts
    assert b["claims"] >= 1                     # bob still sees the shared claim


def test_list_never_returns_a_private_object(corpus):
    eng, panel, ids = corpus
    for kind in ("claim", "evidence"):
        items = panel.list_objects(ids["bob"], kind=kind)
        assert SECRET not in _dump(items)
        hidden = {ids["secret_claim"], ids["secret_ev"]}
        assert all(i["id"] not in hidden for i in items["items"])


def test_overview_stream_and_pulse_carry_no_private_marker(corpus):
    eng, panel, ids = corpus
    ov = panel.overview(ids["bob"])
    assert SECRET not in _dump(ov)


# ---- PRIVATE_GRAPH_LEAK = 0 ----
def test_graph_omits_private_nodes_and_dangling_edges(corpus):
    eng, panel, ids = corpus
    g = panel.knowledge_graph(ids["bob"])
    node_ids = {n["id"] for n in g["nodes"]}
    assert ids["secret_claim"] not in node_ids and ids["secret_ev"] not in node_ids
    assert SECRET not in _dump(g)
    # every edge endpoint is an authorized (present) node — no stub to a hidden neighbour
    for e in g["edges"]:
        assert e["source"] in node_ids and e["target"] in node_ids


def test_expand_cannot_reach_a_private_neighbour(corpus):
    eng, panel, ids = corpus
    g = panel.expand(ids["bob"], ids["shared"])
    assert SECRET not in _dump(g)
    assert ids["secret_claim"] not in {n["id"] for n in g["nodes"]}


# ---- PRIVATE_SEARCH_LEAK = 0 ----
def test_search_never_returns_a_private_hit(corpus):
    eng, panel, ids = corpus
    assert panel.search(ids["bob"], text=SECRET)["results"] == []
    assert len(panel.search(ids["alice"], text=SECRET)["results"]) >= 1  # owner still finds it


# ---- explain / belief / evidence detail : no oracle, no leak ----
def test_belief_and_explain_of_a_private_claim_are_notfound_for_others(corpus):
    eng, panel, ids = corpus
    for who in ("bob", "curator", "outsider"):
        with pytest.raises(NotFoundError):
            panel.belief(ids[who], ids["secret_claim"])
        with pytest.raises(NotFoundError):
            panel.claim_detail(ids[who], ids["secret_claim"])


def test_evidence_detail_of_private_evidence_is_notfound_for_others(corpus):
    eng, panel, ids = corpus
    with pytest.raises(NotFoundError):
        panel.evidence_detail(ids["bob"], ids["secret_ev"])


# ---- cross-tenant is absolute ----
def test_outsider_sees_nothing(corpus):
    eng, panel, ids = corpus
    c = panel.counts(ids["outsider"])
    assert c["knowledge_objects"] == 0
    assert panel.knowledge_graph(ids["outsider"])["nodes"] == []
    assert panel.search(ids["outsider"], text="visible")["results"] == []
    assert SECRET not in _dump(panel.overview(ids["outsider"]))


# ---- visibility composition : a shared claim never exposes private evidence behind it ----
def test_shared_claim_detail_hides_unreadable_evidence(corpus):
    eng, panel, ids = corpus
    # attach alice's PRIVATE evidence to the shared claim; bob reads the claim, not the evidence
    eng.attach_evidence(ids["alice"], evidence_id=ids["secret_ev"], to_claim=ids["shared"],
                        relation="supports")
    detail = panel.claim_detail(ids["bob"], ids["shared"])
    assert SECRET not in _dump(detail)
    assert all(e["evidence"] != ids["secret_ev"] for e in detail["evidence"])
