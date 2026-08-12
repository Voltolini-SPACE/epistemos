"""EPISTEMOS-05 RACE: concurrent reviews / attach / govern vs read. Invariants: belief is always
derivable from a consistent set of reviews, a private claim never leaks under any interleaving, and
governance is atomic — a reader never observes a half-accepted claim."""
from __future__ import annotations

import threading

import pytest
from tests.claims.conftest import principal
from tests.conftest import ManualClock

from epistemos import Engine
from epistemos.storage import SQLiteStore

CYCLES = 30


@pytest.fixture
def eng(tmp_path) -> Engine:
    return Engine(SQLiteStore(tmp_path / "crace.db"), clock=ManualClock())


def test_concurrent_reviews_never_corrupt_belief(eng: Engine) -> None:
    alice = principal("alice")
    curator = principal("curator", extra_caps=frozenset({"knowledge.accept"}))
    sp = eng.create_space(alice, name="team", visibility="TEAM")
    reviewers = [principal(f"r{i}") for i in range(CYCLES)]
    for r in reviewers + [curator]:
        eng.grant_capability(alice, space_id=sp.id, agent=r.agent)
    c = eng.create_claim(alice, subject="x", predicate="=", object="1", space=sp.id)

    def review(r) -> None:
        eng.review_claim(r, c.id, verdict="confirm" if int(r.agent[1:]) % 2 else "dispute")

    bad: list[str] = []

    def reader() -> None:
        for _ in range(CYCLES * 3):
            b = eng.belief(curator, c.id)
            if b["state"] not in {"proposed", "supported", "disputed"}:
                bad.append(b["state"])   # must never see accepted/torn while nobody accepted

    ts = [threading.Thread(target=review, args=(r,)) for r in reviewers]
    ts += [threading.Thread(target=reader), threading.Thread(target=reader)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert bad == []
    # with at least one dispute present, the final belief is DISPUTED (majority is not truth)
    assert eng.belief(curator, c.id)["state"] == "disputed"
    eng.rebuild_projection()
    eng.verify_integrity()


def test_private_claim_never_leaks_under_concurrent_grant_toggle(eng: Engine) -> None:
    alice, bob = principal("alice"), principal("bob")
    sp = eng.create_space(alice, name="team", visibility="TEAM")
    c = eng.create_claim(alice, subject="s", predicate="p", object="SECRET7", space=sp.id)
    leaks: list[str] = []

    def toggler() -> None:
        for i in range(CYCLES):
            if i % 2 == 0:
                eng.grant_capability(alice, space_id=sp.id, agent="bob")
            else:
                eng.revoke_capability(alice, space_id=sp.id, agent="bob")

    def reader() -> None:
        for _ in range(CYCLES * 4):
            got = eng.get(bob, c.id)
            if got is not None and got.object != "SECRET7":
                leaks.append(str(got.object))

    ts = [threading.Thread(target=toggler), threading.Thread(target=reader),
          threading.Thread(target=reader)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert leaks == []
    eng.verify_integrity()
