"""EPISTEMOS-05 CHAOS: after a simulated crash the collaborative state rebuilds FROM THE LEDGER
ALONE — belief, evidence links, governance and space firewall all reconstructed; and there is no
partial acceptance (governance is a single atomic ledger event: recovery sees accepted or not)."""
from __future__ import annotations

from tests.claims.conftest import principal
from tests.conftest import ManualClock

from epistemos import Engine
from epistemos.storage import SQLiteStore

SECRET = "CHAOSCLAIM9"


def _build(eng: Engine) -> str:
    alice = principal("alice")
    bob = principal("bob")
    curator = principal("curator", extra_caps=frozenset({"knowledge.accept"}))
    sp = eng.create_space(alice, name="team", visibility="TEAM")
    for m in (bob, curator):
        eng.grant_capability(alice, space_id=sp.id, agent=m.agent)
    c = eng.create_claim(alice, subject="deal", predicate="value", object=SECRET, space=sp.id)
    ev = eng.create_evidence(alice, title="memo", uri="https://x/m", space=sp.id)
    eng.attach_evidence(alice, evidence_id=ev.id, to_claim=c.id, relation="supports")
    eng.review_claim(bob, c.id, verdict="confirm")
    eng.review_claim(curator, c.id, verdict="dispute", rationale="need audit")
    eng.accept_claim(curator, c.id, reason="override, logged")
    return c.id


def test_collaborative_state_rebuilds_from_ledger_alone(tmp_path) -> None:
    db = tmp_path / "cchaos.db"
    eng = Engine(SQLiteStore(db), clock=ManualClock())
    cid = _build(eng)
    curator = principal("curator", extra_caps=frozenset({"knowledge.accept"}))
    before = eng.explain_claim(curator, cid)
    eng.close()  # committed state == what survives a crash

    eng2 = Engine(SQLiteStore(db), clock=ManualClock())
    assert eng2.verify_integrity() >= 1                       # LEDGER_VALID
    after = eng2.explain_claim(curator, cid)
    assert after == before                                    # STATE fully reconstructed
    # the accepted-with-coexisting-dispute picture survived intact
    assert after["belief"]["state"] == "accepted"
    assert "dispute" in after["belief"]["why"].lower()

    eng2.rebuild_projection()                                 # PROJECTION_REBUILDABLE
    assert eng2.explain_claim(curator, cid) == before
    eng2.close()


def test_no_private_claim_leak_after_recovery(tmp_path) -> None:
    db = tmp_path / "cleak.db"
    eng = Engine(SQLiteStore(db), clock=ManualClock())
    alice = principal("alice")
    c = eng.create_claim(alice, subject="s", predicate="p", object=SECRET)  # PRIVATE
    eng.close()

    eng2 = Engine(SQLiteStore(db), clock=ManualClock())
    stranger = principal("mallory")
    assert eng2.get(stranger, c.id) is None                   # NO_PRIVATE_LEAK
    assert eng2.search(stranger, text=SECRET) == []
    eng2.rebuild_projection()
    assert eng2.get(stranger, c.id) is None
    eng2.close()
