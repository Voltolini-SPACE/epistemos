"""EPISTEMOS-04 CHAOS (§29): after recovery — NO_PRIVATE_LEAK, LEDGER_VALID,
PROJECTION_REBUILDABLE, INDEX_REBUILDABLE, AUTHORIZATION_INTACT."""

from __future__ import annotations

from tests.conftest import ManualClock
from tests.spaces.conftest import principal

from epistemos import Engine
from epistemos.index import IndexHealth
from epistemos.storage import SQLiteStore

SECRET = "CHAOSSECRET5"


def _build(eng: Engine) -> tuple[str, str]:
    alice = principal("alice")
    s = eng.add_source(alice, uri="mem://a", trust=0.9)
    priv = eng.assert_fact(alice, subject="Priv", predicate="is", object=SECRET, source=s.id)
    shared = eng.assert_fact(alice, subject="Shared", predicate="is", object="teamval", source=s.id)
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob")
    eng.share(alice, shared.id, into=team.id)
    return priv.id, shared.id


def test_recovery_preserves_authorization_and_no_leak(tmp_path) -> None:
    db = tmp_path / "chaos.db"
    eng = Engine(SQLiteStore(db), clock=ManualClock())
    priv_id, shared_id = _build(eng)
    eng.close()  # committed WAL state == what survives a crash

    # reopen (simulated restart) — authorization must be reconstructed from the ledger alone
    eng2 = Engine(SQLiteStore(db), clock=ManualClock())
    bob = principal("bob")
    assert eng2.verify_integrity() >= 1                       # LEDGER_VALID
    assert eng2.get(bob, shared_id).object == "teamval"       # AUTHORIZATION_INTACT (granted)
    assert eng2.get(bob, priv_id) is None                     # NO_PRIVATE_LEAK
    assert eng2.search(bob, text=SECRET) == []

    # PROJECTION_REBUILDABLE + INDEX_REBUILDABLE: rebuild and re-check every invariant
    eng2.rebuild_projection()
    assert eng2.verify_index_consistency()
    assert eng2.get(bob, shared_id).object == "teamval"
    assert eng2.get(bob, priv_id) is None
    eng2.close()


def test_index_corruption_does_not_leak_private(tmp_path) -> None:
    """A corrupted FTS index must fall back to the scan WITHOUT leaking a private object."""
    eng = Engine(SQLiteStore(tmp_path / "c.db"), clock=ManualClock())
    priv_id, _ = _build(eng)
    bob = principal("bob")
    # corrupt the FTS content so verify() marks it degraded; search must fall back to the scan
    eng.store._conn.execute("UPDATE fts_idx SET content = content || ' " + SECRET + "'")
    assert eng.verify_index_consistency() is False
    assert eng.lexical_index.health() is IndexHealth.DEGRADED
    # even with a poisoned index, the private fact does not surface for bob
    assert eng.search(bob, text=SECRET) == []
    assert eng.get(bob, priv_id) is None
    eng.rebuild_index()
    assert eng.lexical_index.health() is IndexHealth.HEALTHY
    assert eng.search(bob, text=SECRET) == []
    eng.close()


def test_promotion_survives_rebuild(tmp_path) -> None:
    from epistemos import Principal
    from epistemos.identity import _DEFAULT_CAPS
    eng = Engine(SQLiteStore(tmp_path / "p.db"), clock=ManualClock())
    alice = principal("alice")
    s = eng.add_source(alice, uri="mem://a", trust=0.9)
    f = eng.assert_fact(alice, subject="P", predicate="is", object="open", source=s.id)
    org = eng.create_space(alice, name="org", visibility="ORGANIZATION")
    promoter = Principal(tenant="acme", agent="alice", namespace="hr",
                         capabilities=_DEFAULT_CAPS | {"knowledge.promote"})
    eng.promote(promoter, f.id, into=org.id)
    carol = principal("carol")
    assert eng.get(carol, f.id).object == "open"
    eng.rebuild_projection()
    assert eng.get(carol, f.id).object == "open"  # ORG placement reconstructed from ledger
    eng.close()
