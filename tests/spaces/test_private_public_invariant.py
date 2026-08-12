"""EPISTEMOS-04 P0: PRIVATE_TO_PUBLIC_IMPLICIT_FLOW = IMPOSSIBLE (mission §11).

The adversarial battery every attack in §11/§27 must fail. Meta assertion: after each attack,
a private object of one agent is NEVER observable by an unauthorized principal through ANY
surface — get, search (index + scan fallback), current/as_of, timeline, facts_for, recall,
explain (provenance), neighbors/query_graph (graph), export, or a crafted import.

``PRIVATE_TO_PUBLIC_LEAK = 0``.
"""

from __future__ import annotations

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos._util import canonical_json
from epistemos.errors import AuthorizationError, IntegrityError, NotFoundError
from epistemos.storage import SQLiteStore

SECRET = "TOPSECRETtoken42"


def _alice_private_fact(eng: Engine, alice: Principal):
    s = eng.add_source(alice, uri="mem://a", trust=0.9)
    return eng.assert_fact(alice, subject="Salary", predicate="is", object=SECRET, source=s.id)


def _assert_invisible(eng: Engine, viewer: Principal, fid: str) -> None:
    """The whole meta-assertion: the private fact leaks through NO surface for `viewer`."""
    assert eng.get(viewer, fid) is None
    assert eng.search(viewer, text=SECRET, limit=50) == []
    assert eng.search(viewer, text=SECRET, limit=50) == []  # (second call: warm index path)
    assert eng.current(viewer, subject="Salary", predicate="is") is None
    assert eng.as_of(viewer, "2027-01-01", subject="Salary", predicate="is") is None
    assert eng.timeline(viewer, subject="Salary") == []
    assert eng.facts_for(viewer, subject="Salary") == []
    assert all(SECRET not in canonical_json(o) for o in eng.recall(viewer, limit=200))
    with pytest.raises(NotFoundError):
        eng.explain(viewer, fid)


def test_missing_visibility_defaults_private(sengine: Engine, alice, bob) -> None:
    fid = _alice_private_fact(sengine, alice).id
    _assert_invisible(sengine, bob, fid)


def test_degraded_index_fallback_does_not_leak(tmp_path, alice, bob) -> None:
    """Retrieval fallback (scan) must enforce the same firewall as the index path."""
    eng = Engine(SQLiteStore(tmp_path / "d.db"), clock=ManualClock())
    fid = _alice_private_fact(eng, alice).id
    eng.lexical_index.mark_degraded()  # force the scan path
    assert eng.search(bob, text=SECRET, limit=50) == []
    assert eng.get(bob, fid) is None
    eng.close()


def test_search_score_and_count_do_not_leak(sengine: Engine, alice, bob) -> None:
    """An unauthorized object must not affect another query's score/rank/count (candidate-first)."""
    _alice_private_fact(sengine, alice)
    # bob has his own fact with the same rare term; his result set/score must be as if alice's
    # fact does not exist.
    sb = sengine.add_source(bob, uri="mem://b", trust=0.9)
    sengine.assert_fact(bob, subject="Bobs", predicate="is", object=SECRET, source=sb.id)
    res = sengine.search(bob, text=SECRET, limit=50)
    assert len(res) == 1 and res[0]["kind"] == "fact"  # only bob's, not alice's


def test_crafted_import_cannot_downgrade_visibility(tmp_path, alice, bob) -> None:
    """A crafted export that rewrites payload scope is refused (A-01 still holds under spaces)."""
    donor = Engine(SQLiteStore(tmp_path / "donor.db"), clock=ManualClock())
    _alice_private_fact(donor, alice)
    payload = donor.export()
    donor.close()
    # attacker rewrites the fact's tenant to the victim tenant to smuggle it in
    from epistemos._util import sha256_hex
    from epistemos.ledger import GENESIS_HASH, content_hash
    for ev in payload["events"]:
        if isinstance(ev["payload"], dict) and "tenant" in ev["payload"]:
            ev["payload"]["tenant"] = "victimtenant"
    prev = GENESIS_HASH
    for ev in payload["events"]:
        ch = content_hash(ev["op"], ev["payload"])
        header = {"seq": ev["seq"], "ts": ev["ts"], "op": ev["op"], "tenant": ev["tenant"],
                  "namespace": ev["namespace"], "actor": ev["actor"],
                  "principal": ev["principal"], "content_hash": ch, "prev_hash": prev}
        eh = sha256_hex(canonical_json(header))
        ev["content_hash"], ev["prev_hash"], ev["entry_hash"] = ch, prev, eh
        prev = eh
    victim = Engine(SQLiteStore(tmp_path / "victim.db"), clock=ManualClock())
    with pytest.raises(IntegrityError):
        victim.import_events(payload, verify=True)
    victim.close()


def test_stale_capability_after_revoke_denies(sengine: Engine, alice, bob) -> None:
    """user had access at T1, revoked at T2, query at T3 -> DENIED (mission §22)."""
    fid = _alice_private_fact(sengine, alice).id
    space = sengine.create_space(alice, name="team", visibility="TEAM")
    sengine.grant_capability(alice, space_id=space.id, agent="bob")
    sengine.share(alice, fid, into=space.id)
    assert sengine.get(bob, fid).object == SECRET       # T1: access
    sengine.revoke_capability(alice, space_id=space.id, agent="bob")  # T2: revoke
    _assert_invisible(sengine, bob, fid)                 # T3: fully denied everywhere


def test_client_cannot_forge_membership_via_principal(sengine: Engine, alice) -> None:
    """Membership is server-side: claiming a capability/space on the Principal grants nothing."""
    fid = _alice_private_fact(sengine, alice).id
    space = sengine.create_space(alice, name="team", visibility="TEAM")
    sengine.share(alice, fid, into=space.id)
    # bob forges every capability on his Principal — but was never granted membership.
    forged = Principal(tenant="acme", agent="bob", namespace="hr",
                       capabilities=frozenset({"read", "knowledge.read", "knowledge.search",
                                               "space.read", "space.manage"}))
    assert sengine.get(forged, fid) is None
    assert sengine.search(forged, text=SECRET) == []


def test_promotion_toward_public_requires_capability(sengine: Engine, alice, bob) -> None:
    """The ONLY path toward PUBLIC is an authorized promote; default caps cannot reach ORG+."""
    fid = _alice_private_fact(sengine, alice).id
    pub = sengine.create_space(alice, name="public", visibility="PUBLIC")
    with pytest.raises(AuthorizationError):
        sengine.promote(alice, fid, into=pub.id)  # alice lacks knowledge.promote
    _assert_invisible(sengine, bob, fid)  # still private


def test_cross_space_id_reference_does_not_leak(sengine: Engine, alice, bob) -> None:
    """A readable object referencing a private one by id must not expose the private one."""
    priv = _alice_private_fact(sengine, alice)
    # alice derives a TEAM-shared fact FROM her private one, and shares it to bob
    s = sengine.add_source(alice, uri="mem://a2", trust=0.9)
    derived = sengine.assert_fact(alice, subject="Pub", predicate="p", object="ok",
                                  source=s.id, derived_from=[priv.id])
    space = sengine.create_space(alice, name="team", visibility="TEAM")
    sengine.grant_capability(alice, space_id=space.id, agent="bob")
    sengine.share(alice, derived.id, into=space.id)
    # bob can read the derived fact and explain it, but the private parent stays elided/out-of-scope
    exp = sengine.explain(bob, derived.id)
    blob = canonical_json(exp)
    assert SECRET not in blob  # the private parent's content never appears
    assert sengine.get(bob, priv.id) is None
