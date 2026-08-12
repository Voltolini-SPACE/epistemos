"""Engine-failure injection + knowledge-integrity invariants (EPISTEMOS-PANEL-HARDENING-01 §9/§10).

Two guarantees:

* **Fail explicitly, never fabricate.** When the store errors or an object is missing, the panel
  raises / 404s — it never returns partial or invented data, and never turns UNKNOWN into success.
* **The UI never collapses the model's distinctions:** claim ≠ evidence ≠ review ≠ acceptance ≠
  decision, majority ≠ truth, claimant ≠ ingester, transaction-time ≠ valid-time.
"""
from __future__ import annotations

import http.client
import threading

import pytest
from tests.panel.conftest import principal

from epistemos import Engine
from epistemos.api.panel import PanelService
from epistemos.api.server import make_panel_server
from epistemos.errors import NotFoundError
from epistemos.storage import MemoryStore


class _FaultyStore:
    """Delegates to a real store but raises inside a chosen method (Engine/storage failure)."""

    def __init__(self, inner, fail_on: str) -> None:
        self._inner = inner
        self._fail_on = fail_on

    def __getattr__(self, name):
        if name == self._fail_on:
            def boom(*a, **k):
                raise RuntimeError("injected storage failure")
            return boom
        return getattr(self._inner, name)


def _alice(eng):
    return principal("alice", extra=frozenset({"claim.confirm", "claim.dispute",
                                               "knowledge.accept", "claim.retract"}))


# ---- failure injection: fail loud, never fabricate ----
def test_store_failure_propagates_not_fabricated():
    eng = Engine(MemoryStore())
    a = _alice(eng)
    eng.create_claim(a, subject="X", predicate="is", object="Y")
    panel = PanelService(eng)
    eng.store = _FaultyStore(eng.store, "objects")  # reads now explode
    for call in (lambda: panel.counts(a), lambda: panel.overview(a),
                 lambda: panel.knowledge_graph(a), lambda: panel.list_objects(a, kind="claim")):
        with pytest.raises(Exception):  # noqa: B017 - any exception, but it MUST raise (no fake data)
            call()
    eng.close()


def test_store_failure_over_http_is_500_safe_not_fabricated():
    eng = Engine(MemoryStore())
    a = _alice(eng)
    eng.create_claim(a, subject="Secret", predicate="is", object="TOPSECRETMARK")
    eng.store = _FaultyStore(eng.store, "objects")
    srv = make_panel_server(eng, host="127.0.0.1", port=0, tokens={"A": a})
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    c = http.client.HTTPConnection(host, port, timeout=5)
    c.request("GET", "/api/overview", headers={"Authorization": "Bearer A"})
    r = c.getresponse()
    body = r.read()
    assert r.status == 500
    # a failure is reported as a generic internal error — no fabricated payload, no internals leaked
    assert b"TOPSECRETMARK" not in body
    assert b"injected storage failure" not in body and b"Traceback" not in body
    assert b"internal error" in body
    c.close()
    srv.shutdown()
    srv.server_close()
    eng.close()


def test_missing_object_is_notfound_never_invented():
    eng = Engine(MemoryStore())
    a = _alice(eng)
    panel = PanelService(eng)
    for call in (lambda: panel.claim_detail(a, "clm_" + "0" * 32),
                 lambda: panel.belief(a, "clm_" + "0" * 32),
                 lambda: panel.evidence_detail(a, "evd_" + "0" * 32),
                 lambda: panel.explain(a, "clm_" + "0" * 32)):
        with pytest.raises(NotFoundError):
            call()
    eng.close()


# ---- integrity invariants: the UI never collapses the model ----
def test_majority_is_not_truth():
    eng = Engine(MemoryStore())
    a = principal("alice", extra=frozenset({"claim.confirm", "claim.dispute", "knowledge.share"}))
    bob = principal("bob", extra=frozenset({"claim.confirm"}))
    carol = principal("carol", extra=frozenset({"claim.dispute"}))
    team = eng.create_space(a, name="team", visibility="TEAM")
    eng.grant_capability(a, space_id=team.id, agent="bob")
    eng.grant_capability(a, space_id=team.id, agent="carol")
    claim = eng.create_claim(a, subject="X", predicate="acquired", object="Y", space=team.id)
    eng.review_claim(a, claim.id, verdict="confirm")
    eng.review_claim(bob, claim.id, verdict="confirm")
    eng.review_claim(carol, claim.id, verdict="dispute")  # 2 confirm vs 1 dispute
    panel = PanelService(eng)
    counts = panel.counts(a)
    # a single dispute makes the claim DISPUTED — the 2-to-1 majority does not make it "supported"
    assert counts["disputed"] == 1 and counts["supported"] == 0
    eng.close()


def test_claimant_is_distinct_from_ingester():
    eng = Engine(MemoryStore())
    hermes = principal("hermes")  # the ingesting agent
    claim = eng.create_claim(hermes, subject="X", predicate="acquired", object="Y",
                             claimant="analyst_jo", contributor_kind="human")
    panel = PanelService(eng)
    detail = panel.claim_detail(hermes, claim.id)
    blob = str(detail)
    # the human claimant and the ingesting agent are both present and different
    assert "analyst_jo" in blob and "hermes" in blob
    eng.close()


def test_kinds_are_counted_separately():
    eng = Engine(MemoryStore())
    a = _alice(eng)
    claim = eng.create_claim(a, subject="X", predicate="is", object="Y")
    ev = eng.create_evidence(a, title="doc", uri="u")
    eng.attach_evidence(a, evidence_id=ev.id, to_claim=claim.id, relation="supports")
    eng.review_claim(a, claim.id, verdict="confirm")
    eng.add_source(a, uri="s", trust=0.5)
    panel = PanelService(eng)
    c = panel.counts(a)
    # claim, evidence, review, source are each their own kind — never merged
    assert c["claims"] == 1 and c["evidence"] == 1 and c["reviews"] == 1 and c["sources"] == 1
    assert c["knowledge_objects"] == c["claims"] + c["evidence"] + c["reviews"] + c["sources"] \
        + c["entities"] + c["facts"] + c["decisions"]
    eng.close()
