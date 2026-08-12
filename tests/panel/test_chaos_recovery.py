"""Chaos / recovery for the panel read-model (EPISTEMOS-PANEL-HARDENING-01 §20).

The panel state is a projection of the append-only ledger. A crash/restart is modelled by wiping
the projection and rebuilding it from the ledger: the authorized views the panel serves must be
byte-identical before and after — recovery never silently corrupts what a principal sees.
"""
from __future__ import annotations

import json

import pytest
from tests.panel.conftest import SECRET, principal

from epistemos import Engine
from epistemos.api.panel import PanelService
from epistemos.storage import MemoryStore


@pytest.fixture
def built():
    eng = Engine(MemoryStore())
    alice = principal("alice",
                      extra=frozenset({"knowledge.share", "claim.confirm", "claim.retract"}))
    bob = principal("bob")
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob")
    src = eng.add_source(alice, uri="https://s", trust=0.8)
    for i in range(6):
        c = eng.create_claim(alice, subject=f"S{i}", predicate="is", object=f"o{i}",
                             space=team.id, source=src.id)
        ev = eng.create_evidence(alice, title=f"e{i}", uri=f"https://e/{i}", space=team.id)
        eng.attach_evidence(alice, evidence_id=ev.id, to_claim=c.id, relation="supports")
        eng.review_claim(alice, c.id, verdict="confirm")
        if i == 0:
            eng.retract_claim(alice, c.id, reason="chaos")
    eng.create_claim(alice, subject="Secret", predicate="is", object=SECRET)  # private
    yield eng, PanelService(eng), alice, bob
    eng.close()


def _snapshot(panel, who):
    # a stable, order-independent view of what the panel serves this principal
    return {
        "counts": panel.counts(who),
        "graph_nodes": sorted(n["id"] for n in panel.knowledge_graph(who)["nodes"]),
        "graph_edges": sorted(
            json.dumps(e, sort_keys=True) for e in panel.knowledge_graph(who)["edges"]),
        "claims": sorted(i["id"] for i in panel.list_objects(who, kind="claim")["items"]),
    }


def test_projection_rebuild_preserves_panel_views(built):
    eng, panel, alice, bob = built
    before_alice = _snapshot(panel, alice)
    before_bob = _snapshot(panel, bob)

    # crash/restart: wipe the projection and replay the ledger
    rebuilt = eng.rebuild_projection()
    assert rebuilt > 0

    after_alice = _snapshot(panel, alice)
    after_bob = _snapshot(panel, bob)
    assert after_alice == before_alice, "alice's panel view changed after ledger replay"
    assert after_bob == before_bob, "bob's panel view changed after ledger replay"
    # and the firewall still holds after recovery: bob never sees the private marker
    assert SECRET not in json.dumps(after_bob)
    assert SECRET not in json.dumps(panel.overview(bob), default=str)


def test_rebuild_is_idempotent(built):
    eng, panel, alice, bob = built
    eng.rebuild_projection()
    once = _snapshot(panel, alice)
    eng.rebuild_projection()
    twice = _snapshot(panel, alice)
    assert once == twice  # replaying again changes nothing (deterministic recovery)
