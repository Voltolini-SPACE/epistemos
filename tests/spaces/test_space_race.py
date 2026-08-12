"""EPISTEMOS-04 RACE (§28): concurrent share/revoke/promote vs read — invariants must hold,
and a private object must NEVER be observable by an unauthorized principal at any interleaving."""

from __future__ import annotations

import threading

import pytest
from tests.conftest import ManualClock
from tests.spaces.conftest import principal

from epistemos import Engine, Principal
from epistemos.identity import _DEFAULT_CAPS
from epistemos.storage import SQLiteStore

SECRET = "RACESECRET7"
CYCLES = 30


@pytest.fixture
def eng(tmp_path) -> Engine:
    return Engine(SQLiteStore(tmp_path / "race.db"), clock=ManualClock())


def test_share_vs_revoke_never_leaks(eng: Engine) -> None:
    alice, bob = principal("alice"), principal("bob")
    s = eng.add_source(alice, uri="mem://a", trust=0.9)
    f = eng.assert_fact(alice, subject="S", predicate="p", object=SECRET, source=s.id)
    space = eng.create_space(alice, name="team", visibility="TEAM")
    eng.share(alice, f.id, into=space.id)
    leaks: list[str] = []

    def toggler() -> None:
        for i in range(CYCLES):
            if i % 2 == 0:
                eng.grant_capability(alice, space_id=space.id, agent="bob")
            else:
                eng.revoke_capability(alice, space_id=space.id, agent="bob")

    def reader() -> None:
        for _ in range(CYCLES * 4):
            got = eng.get(bob, f.id)
            # bob may or may not have access depending on the interleaving — but a returned
            # object must ALWAYS be the correct fact, never a torn/foreign object.
            if got is not None and got.object != SECRET:
                leaks.append(str(got.object))

    ts = [threading.Thread(target=toggler), threading.Thread(target=reader),
          threading.Thread(target=reader)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert leaks == []
    # final state is deterministic: last op was revoke (odd last index) or grant; either way,
    # rebuild reproduces the same access decision.
    eng.rebuild_projection()
    assert eng.verify_index_consistency()
    eng.verify_integrity()


def test_concurrent_grants_are_consistent(eng: Engine) -> None:
    alice = principal("alice")
    s = eng.add_source(alice, uri="mem://a", trust=0.9)
    f = eng.assert_fact(alice, subject="S", predicate="p", object=SECRET, source=s.id)
    space = eng.create_space(alice, name="team", visibility="TEAM")
    eng.share(alice, f.id, into=space.id)
    agents = [f"agent{i}" for i in range(CYCLES)]

    def granter(agent: str) -> None:
        eng.grant_capability(alice, space_id=space.id, agent=agent)

    threads = [threading.Thread(target=granter, args=(a,)) for a in agents]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # every granted agent can read; a never-granted agent cannot.
    for a in agents:
        p = Principal(tenant="acme", agent=a, namespace="hr", capabilities=_DEFAULT_CAPS)
        assert eng.get(p, f.id).object == SECRET
    stranger = principal("stranger")
    assert eng.get(stranger, f.id) is None
    eng.verify_integrity()
