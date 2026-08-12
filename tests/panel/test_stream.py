"""PRIVATE_STREAM_LEAK = 0 (mission §34): the authorized event stream is filtered at the source.
No private event, and no raw payload, ever reaches an unauthorized consumer."""
from __future__ import annotations

import json

from tests.panel.conftest import SECRET

from epistemos.api.stream import authorized_events, event_kind_for


def test_stream_drops_private_events(corpus):
    eng, panel, ids = corpus
    bob_evts = authorized_events(eng, ids["bob"])
    assert SECRET not in json.dumps(bob_evts, default=str)
    assert all(e["object"] not in (ids["secret_claim"], ids["secret_ev"]) for e in bob_evts)
    # the owner does see her private object's events
    alice_evts = authorized_events(eng, ids["alice"])
    assert any(e["object"] == ids["secret_claim"] for e in alice_evts)


def test_stream_envelope_is_redacted_not_the_raw_payload(corpus):
    eng, panel, ids = corpus
    safe_keys = {"seq", "op", "kind", "ts", "actor", "object", "object_kind", "summary"}
    for e in authorized_events(eng, ids["bob"]):
        # only the safe, fixed envelope keys — never arbitrary payload fields
        assert set(e.keys()) == safe_keys


def test_stream_is_cross_tenant_closed(corpus):
    eng, panel, ids = corpus
    assert authorized_events(eng, ids["outsider"]) == []


def test_stream_resumes_by_seq(corpus):
    eng, panel, ids = corpus
    allev = authorized_events(eng, ids["alice"])
    assert allev, "expected some authorized events"
    mid = allev[len(allev) // 2]["seq"]
    tail = authorized_events(eng, ids["alice"], since_seq=mid)
    assert all(e["seq"] > mid for e in tail)                 # no re-delivery of already-seen events
    assert len(tail) < len(allev)


def test_event_kind_mapping_is_stable(corpus):
    assert event_kind_for("claim_asserted") == "claim.created"
    assert event_kind_for("evidence_attached") == "evidence.attached"
    assert event_kind_for("knowledge_totally_unknown_op") == "knowledge_totally_unknown_op"
