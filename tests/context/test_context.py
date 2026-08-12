"""Context Envelope — behaviour + security (EPISTEMOS v0.6, promoted).

Behaviour: contradictions pinned (incl. attached), safe redundancy collapse only for a confident
current-state intent, history preserved otherwise, corroboration never collapsed, honest
``context_incomplete``.

Security (``PRIVATE_CONTEXT_LEAK = 0``): the envelope is built over ``search`` output and never
widens it; the only relation it follows — a claim's attached contradiction — is re-authorized. A
private object (a private prior version, a private contradiction, a private anything) never appears
in another principal's envelope: not delivered, not collapsed, not behind a handle.
"""

from __future__ import annotations

import json

import pytest

from epistemos import Engine, Principal
from epistemos.context import ContextEnvelopeBuilder, EnvelopeConfig, classify_intent
from epistemos.identity import _DEFAULT_CAPS
from epistemos.storage import MemoryStore

SECRET = "SECRETXYZ_ctx_marker"
CAPS = _DEFAULT_CAPS | frozenset({"supersede", "decide", "knowledge.share", "space.create"})


def _p(agent: str, tenant: str = "acme") -> Principal:
    return Principal(tenant=tenant, agent=agent, namespace="kb", capabilities=CAPS)


def _ctx(eng, principal, query, **kw):
    return eng.context(principal, query, **kw)


# ---- intent classification (conservative) ---------------------------------
@pytest.mark.parametrize("q,intent,conf", [
    ("what database do we use now", "current", "high"),
    ("what did we use before postgres", "historical", "high"),
    ("what changed in our datastore", "change", "high"),
    ("why did we adopt postgres", "decision", "high"),
    ("is this still disputed", "contradiction", "high"),
    ("tell me about the widget", "current", "low"),          # ambiguous → low → no collapse
])
def test_intent_classification(q, intent, conf):
    assert classify_intent(q) == (intent, conf)


# ---- behaviour ------------------------------------------------------------
def test_current_intent_collapses_history_but_keeps_it_reachable():
    eng = Engine(MemoryStore())
    a = _p("alice")
    f = eng.assert_fact(a, subject="Datastore", predicate="is", object="mongo")
    chain = [f.id]
    for v in ("mysql", "postgres"):
        f = eng.supersede(a, f.id, new={"object": v}, reason="x")
        chain.append(f.id)
    env = eng.context(a, "Datastore", intent="current")
    reach = {i["object"] for i in env["items"]}
    for g in env["collapsed_groups"]:
        reach.update(g["collapsed"])
        reach.add(g["current"])
    assert chain[-1] in {i["object"] for i in env["items"]}   # current delivered inline
    assert set(chain) <= reach                                # all versions reachable
    assert env["token_estimate"] < sum(1 for _ in chain) * 30  # fewer tokens than dumping all
    assert env["context_incomplete"] and "history_collapsed" in env["incomplete_reasons"]


def test_historical_intent_preserves_history():
    eng = Engine(MemoryStore())
    a = _p("alice")
    f = eng.assert_fact(a, subject="Datastore", predicate="is", object="mongo")
    for v in ("mysql", "postgres"):
        f = eng.supersede(a, f.id, new={"object": v}, reason="x")
    env = eng.context(a, "Datastore", intent="historical")
    assert len(env["items"]) == 3 and not env["collapsed_groups"]


def test_ambiguous_intent_does_not_collapse():
    eng = Engine(MemoryStore())
    a = _p("alice")
    f = eng.assert_fact(a, subject="Widget", predicate="is", object="v1")
    for v in ("v2", "v3"):
        f = eng.supersede(a, f.id, new={"object": v}, reason="x")
    env = eng.context(a, "Widget")   # no intent → current/low → conservative, no collapse
    assert not env["collapsed_groups"]


def test_attached_contradiction_is_pinned():
    eng = Engine(MemoryStore())
    a = _p("alice")
    c = eng.create_claim(a, subject="Costs", predicate="are", object="fine")
    ev = eng.create_evidence(a, title="bill spiked", uri="mem://b",
                             metadata={"relation": "contradicts"})
    eng.attach_evidence(a, evidence_id=ev.id, to_claim=c.id, relation="contradicts")
    env = eng.context(a, "Costs", intent="contradiction")
    assert ev.id in env["pinned_contradictions"]
    assert ev.id in {i["object"] for i in env["items"]}


def test_true_duplicates_collapse_but_stay_reachable():
    eng = Engine(MemoryStore())
    a = _p("alice")
    d1 = eng.create_evidence(a, title="SOC2 passed", uri="mem://d1", content_hash="soc2")
    d2 = eng.create_evidence(a, title="SOC2 passed", uri="mem://d2", content_hash="soc2")
    env = eng.context(a, "SOC2", intent="current")
    delivered = {i["object"] for i in env["items"]}
    dup_groups = [g for g in env["collapsed_groups"] if g["kind"] == "duplicate"]
    assert dup_groups, "identical content_hash must collapse into a duplicate group"
    assert len({d1.id, d2.id} & delivered) == 1               # only one representative inline
    reach = set(delivered)
    for g in env["collapsed_groups"]:
        reach.update(g["collapsed"])
        reach.add(g["current"])
    assert {d1.id, d2.id} <= reach                            # both reachable (nothing lost)


def test_corroboration_is_not_collapsed():
    eng = Engine(MemoryStore())
    a = _p("alice")
    # SAME finding/title, DIFFERENT source (uri), NO content_hash ⇒ corroboration, not a dup.
    # Only identical content_hash may collapse; keying by title would wrongly fold these.
    e1 = eng.create_evidence(a, title="Revenue grew", uri="mem://firmA")
    e2 = eng.create_evidence(a, title="Revenue grew", uri="mem://firmB")
    env = eng.context(a, "Revenue grew", intent="current")
    delivered = {i["object"] for i in env["items"]}
    assert e1.id in delivered and e2.id in delivered          # both independent sources survive
    assert not [g for g in env["collapsed_groups"] if g["kind"] == "duplicate"]


# ---- security -------------------------------------------------------------
@pytest.fixture
def two_principals():
    eng = Engine(MemoryStore())
    alice, bob = _p("alice"), _p("bob")
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob")
    # a fact whose PRIOR version is private (marker) and CURRENT version is shared
    f = eng.assert_fact(alice, subject="Deploy", predicate="is", object=SECRET)  # private prior
    priv_ver = f.id
    f2 = eng.supersede(alice, f.id, new={"object": "production"}, reason="done")
    eng.share(alice, f2.id, into=team.id)
    yield eng, alice, bob, priv_ver, f2.id


def test_private_prior_version_never_leaks(two_principals):
    eng, alice, bob, priv_ver, shared_ver = two_principals
    env = eng.context(bob, "Deploy", intent="current")
    blob = json.dumps(env)
    assert SECRET not in blob                                  # PRIVATE_CONTEXT_LEAK = 0
    reach = {i["object"] for i in env["items"]}
    for g in env["collapsed_groups"]:
        reach.update(g["collapsed"])
        reach.add(g["current"])
    assert priv_ver not in reach                               # private prior never reachable


def test_private_contradiction_attached_to_shared_claim_no_leak():
    eng = Engine(MemoryStore())
    alice, bob = _p("alice"), _p("bob")
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob")
    claim = eng.create_claim(alice, subject="Widget", predicate="is", object="fine", space=team.id)
    priv_ev = eng.create_evidence(alice, title=SECRET, uri="mem://x",
                                  metadata={"relation": "contradicts"})   # private to alice
    eng.attach_evidence(alice, evidence_id=priv_ev.id, to_claim=claim.id, relation="contradicts")
    env = eng.context(bob, "Widget", intent="contradiction")
    assert SECRET not in json.dumps(env)
    assert priv_ev.id not in {i["object"] for i in env["items"]}
    # alice (owner) DOES get it pinned
    aenv = eng.context(alice, "Widget", intent="contradiction")
    assert priv_ev.id in {i["object"] for i in aenv["items"]}


def test_cross_tenant_no_leak(two_principals):
    eng, alice, *_ = two_principals
    outsider = _p("mallory", tenant="evilcorp")
    env = eng.context(outsider, "Deploy", intent="current")
    assert env["items"] == []
    assert SECRET not in json.dumps(env)


def test_builder_uses_engine_config_default():
    # the shipped default enables pinning + collapse; experimental knobs are off
    cfg = EnvelopeConfig()
    assert cfg.pin_contradictions and cfg.collapse_redundancy
    assert not cfg.budget_pack and not cfg.continuation


def test_compact_false_returns_raw():
    eng = Engine(MemoryStore())
    a = _p("alice")
    eng.assert_fact(a, subject="A", predicate="is", object="1")
    raw = eng.context(a, "A", compact=False)
    assert raw["format"] == "raw" and "results" in raw


def test_race_concurrent_context(two_principals):
    import threading
    eng, alice, bob, *_ = two_principals
    errors: list[str] = []
    b = ContextEnvelopeBuilder(eng)

    def worker() -> None:
        for _ in range(30):
            try:
                for pr, it in ((alice, "current"), (bob, "current"), (alice, "historical")):
                    json.dumps(b.build(pr, "Deploy", config=EnvelopeConfig(), intent=it).to_dict())
            except Exception as e:  # noqa: BLE001
                errors.append(f"{type(e).__name__}: {e}")

    ts = [threading.Thread(target=worker) for _ in range(6)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errors
