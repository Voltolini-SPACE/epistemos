"""Guards the single-pass read-model optimization (EPISTEMOS-PANEL-HARDENING-01 §15).

`_readable_by_kinds` replaced N per-kind store scans with one bucketed pass (3-5x faster on the
aggregate views at 10k objects). This pins that the optimization is *semantically identical* to the
per-kind path — same objects, same firewall — so speed never came at the cost of correctness.
"""
from __future__ import annotations

import pytest
from tests.panel.conftest import principal

from epistemos import Engine
from epistemos.api.panel import GRAPH_KINDS, PanelService
from epistemos.storage import MemoryStore


@pytest.fixture
def corpus_panel():
    eng = Engine(MemoryStore())
    alice = principal("alice", extra=frozenset({"knowledge.share", "claim.confirm"}))
    bob = principal("bob")
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob")
    src = eng.add_source(alice, uri="https://s", trust=0.7)
    for i in range(8):
        sp = team.id if i % 2 == 0 else None  # mix of shared and private
        c = eng.create_claim(alice, subject=f"S{i}", predicate="is", object=f"o{i}",
                             space=sp, source=src.id)
        ev = eng.create_evidence(alice, title=f"e{i}", uri=f"https://e/{i}", space=sp)
        eng.attach_evidence(alice, evidence_id=ev.id, to_claim=c.id, relation="supports")
        eng.review_claim(alice, c.id, verdict="confirm")
    yield eng, PanelService(eng), alice, bob
    eng.close()


@pytest.mark.parametrize("who", ["alice", "bob"])
def test_single_pass_matches_per_kind(corpus_panel, who):
    eng, panel, alice, bob = corpus_panel
    principal_ = alice if who == "alice" else bob
    grouped = panel._readable_by_kinds(principal_, GRAPH_KINDS)
    for kind in GRAPH_KINDS:
        expected = {o["id"] for o in panel._readable_of_kind(principal_, kind)}
        got = {o["id"] for o in grouped[kind]}
        assert got == expected, f"{who}/{kind}: single-pass {got} != per-kind {expected}"
