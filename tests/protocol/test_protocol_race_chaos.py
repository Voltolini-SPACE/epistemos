"""EPCTX protocol — race (§30) and chaos (§31).

Race: many threads build documents and redeem handles while the store is mutated concurrently
(supersede, contradiction attach, capability revoke). No crash, no cross-principal contamination, no
private leak. Chaos: a rebuilt engine reproduces the same document; a redemption against a shrunken
store returns a partial-but-honest result rather than crashing.
"""

from __future__ import annotations

import json
import threading

from epistemos import Engine
from epistemos.protocol import build_epctx, canonical_json
from epistemos.storage import MemoryStore

from .conftest import principal, seed

SECRET = "SECRETXYZ_race_marker"


def test_race_context_vs_mutation_30x():
    eng = Engine(MemoryStore())
    alice = principal("alice")
    f = eng.assert_fact(alice, subject="Datastore", predicate="is", object="v0")
    errors: list[str] = []

    def reader() -> None:
        for _ in range(30):
            try:
                doc = eng.epctx(alice, "Datastore", intent="current")
                assert doc["protocol_version"] == "EPCTX/1"
            except Exception as e:  # noqa: BLE001
                errors.append(f"{type(e).__name__}: {e}")

    def writer() -> None:
        nonlocal f
        for i in range(30):
            try:
                f = eng.supersede(alice, f.id, new={"object": f"v{i + 1}"}, reason="m")
            except Exception as e:  # noqa: BLE001
                errors.append(f"writer {type(e).__name__}: {e}")

    threads = [threading.Thread(target=reader) for _ in range(4)] + \
              [threading.Thread(target=writer)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors[:3]


def test_race_two_principals_no_contamination_30x():
    eng = Engine(MemoryStore())
    alice, bob = principal("alice"), principal("bob")
    eng.assert_fact(alice, subject="Deploy", predicate="is", object=SECRET)   # private to alice
    eng.assert_fact(bob, subject="Deploy", predicate="is", object="bob-value")
    leaks: list[str] = []

    def bob_reader() -> None:
        for _ in range(30):
            doc = eng.epctx(bob, "Deploy", intent="current")
            if SECRET in json.dumps(doc, default=str):
                leaks.append("LEAK")

    ts = [threading.Thread(target=bob_reader) for _ in range(6)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not leaks


def test_race_expansion_vs_revoke_30x():
    eng = Engine(MemoryStore())
    alice, bob = principal("alice"), principal("bob")
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob",
                         capabilities=("knowledge.read", "assert", "supersede"))
    f = eng.assert_fact(alice, subject="Shared", predicate="is", object=SECRET)
    f2 = eng.supersede(alice, f.id, new={"object": "v2"}, reason="m")
    eng.share(alice, f.id, into=team.id)
    eng.share(alice, f2.id, into=team.id)
    leaks: list[str] = []

    def churn() -> None:
        for _ in range(30):
            doc = eng.epctx(bob, "Shared", intent="current")
            for h in doc["expansion"]["handles"]:
                out = eng.expand(bob, h["handle"])
                if SECRET in json.dumps(out, default=str) and not out.get("authorized"):
                    leaks.append("LEAK")

    def revoker() -> None:
        for _ in range(30):
            try:
                eng.revoke_capability(alice, space_id=team.id, agent="bob")
                eng.grant_capability(alice, space_id=team.id, agent="bob",
                                     capabilities=("knowledge.read",))
            except Exception:  # noqa: BLE001,S110
                pass

    ts = [threading.Thread(target=churn) for _ in range(3)] + [threading.Thread(target=revoker)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not leaks


# ---- chaos (§31) ----------------------------------------------------------
def test_chaos_rebuild_reproduces_document():
    docs = []
    for _ in range(3):
        eng = Engine(MemoryStore())
        alice = principal("alice")
        seed(eng, alice)
        d = build_epctx(eng, alice, query="Datastore", intent="historical")
        d["expansion"] = {}
        d["integrity"] = {}
        # ids/timestamps differ across rebuilds; compare the semantic shape
        shape = {
            "sections": {k: len(v) for k, v in d["context"].items()},
            "disputed": d["disputed"],
            "completeness": d["completeness"],
            "temporal": d["temporal"],
            "tokens_by_section": d["tokens_by_section"],
        }
        docs.append(canonical_json(shape))
    assert len(set(docs)) == 1, "rebuild must reproduce the same document shape"


def test_chaos_expand_against_shrunken_store_is_partial_not_crash():
    eng = Engine(MemoryStore())
    alice = principal("alice")
    f = eng.assert_fact(alice, subject="Datastore", predicate="is", object="v0")
    eng.supersede(alice, f.id, new={"object": "v1"}, reason="m")
    doc = eng.epctx(alice, "Datastore", intent="current")
    handle = doc["expansion"]["handles"][0]["handle"]
    # simulate a degraded store where a member object can no longer be fetched
    orig = eng.store.get_object

    def flaky(oid: str):  # type: ignore[no-untyped-def]
        return None if oid.startswith("fact_") else orig(oid)

    eng.store.get_object = flaky  # type: ignore[method-assign]
    try:
        out = eng.expand(alice, handle)
    finally:
        eng.store.get_object = orig  # type: ignore[method-assign]
    # honest partial: authorized, but members dropped and marked incomplete — never a crash/leak
    assert out["authorized"] is True
    assert out["complete"] is False
