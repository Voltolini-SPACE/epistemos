"""EPISTEMOS-03 audit: in-place mutation of another agent's object stays owner-guarded,
and the additive primitives cannot be used subtractively.

Findings B-03 (confirm negative delta), B-04 (merge/split owner guard), B-06 (cross-scope
source dereference). Together these keep the agent-isolation and tenant-isolation invariants
whole across the *entire* mutation and read surface, not just supersede/retract/correct.

The design (test_agent_isolation.py) is: additive operations (confirm corroboration, recording a
contradiction) are allowed cross-agent; operations that *clobber* an existing object are not.
The audit found three leaks in that model:

* ``confirm(delta<0)`` turns "add corroboration" into "lower a rival's confidence" — subtractive.
* ``merge_entities`` / ``split_entity`` rewrite an existing entity in place with no owner guard.
* source pointers are dereferenced for display/authority with no scope check, so a fact whose
  ``source`` dangles into another tenant leaks that source's URI and trust.
"""

from __future__ import annotations

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos._util import canonical_json
from epistemos.errors import AuthorizationError, ValidationError
from epistemos.storage import SQLiteStore

ALICE = Principal(tenant="acme", agent="alice", namespace="shared")
BOB = Principal(tenant="acme", agent="bob", namespace="shared")


def test_confirm_rejects_negative_delta(engine: Engine) -> None:
    """B-03: confirm is corroboration; it may only raise confidence, never lower it."""
    s = engine.add_source(ALICE, uri="mem://s", trust=0.9)
    f = engine.assert_fact(ALICE, subject="A", predicate="p", object="X",
                           source=s.id, confidence=0.9)
    sb = engine.add_source(BOB, uri="mem://b", trust=0.9)
    with pytest.raises(ValidationError, match="non-negative"):
        engine.confirm(BOB, f.id, source=sb.id, delta_confidence=-1.0)
    # confidence is untouched
    assert engine.get(ALICE, f.id).confidence == 0.9
    # a non-negative confirm still works (additive, cross-agent, as designed)
    engine.confirm(BOB, f.id, source=sb.id, delta_confidence=0.05)
    assert engine.get(ALICE, f.id).confidence == pytest.approx(0.95)


def test_merge_entities_is_owner_guarded(engine: Engine) -> None:
    """B-04: merge rewrites the canonical entity in place — another agent may not."""
    e1 = engine.add_entity(ALICE, name="Canonical")
    e2 = engine.add_entity(ALICE, name="Dup")
    with pytest.raises(AuthorizationError):
        engine.merge_entities(BOB, canonical=e1.id, duplicates=[e2.id], aliases=["INJECTED"])
    assert "INJECTED" not in engine.get(ALICE, e1.id).aliases


def test_split_entity_is_owner_guarded(engine: Engine) -> None:
    """B-04: split annotates the origin entity in place — another agent may not."""
    e = engine.add_entity(ALICE, name="Origin")
    with pytest.raises(AuthorizationError):
        engine.split_entity(BOB, e.id, into=[dict(name="Fragment")])
    assert "split_into" not in engine.get(ALICE, e.id).metadata


def test_admin_may_merge_and_split(engine: Engine) -> None:
    from epistemos.identity import _DEFAULT_CAPS
    admin = Principal(tenant="acme", agent="root", namespace="shared",
                      capabilities=_DEFAULT_CAPS | {"admin"})
    e1 = engine.add_entity(ALICE, name="C")
    e2 = engine.add_entity(ALICE, name="D")
    engine.merge_entities(admin, canonical=e1.id, duplicates=[e2.id])  # allowed
    engine.split_entity(admin, e1.id, into=[dict(name="E")])  # allowed


def test_same_agent_merge_split_still_work(engine: Engine) -> None:
    """Anti-regression: an agent merging/splitting its OWN entities is unaffected."""
    e1 = engine.add_entity(ALICE, name="C")
    e2 = engine.add_entity(ALICE, name="D")
    engine.merge_entities(ALICE, canonical=e1.id, duplicates=[e2.id])
    engine.split_entity(ALICE, e1.id, into=[dict(name="E")])


def _sqlite_engine(tmp_path) -> Engine:
    return Engine(SQLiteStore(tmp_path / "s.db"), clock=ManualClock())


def test_source_deref_never_crosses_scope(tmp_path) -> None:
    """B-06: a fact whose source pointer dangles into another tenant must not leak the URI."""
    eng = _sqlite_engine(tmp_path)
    other = Principal(tenant="globex", agent="g", namespace="hr")
    secret = eng.add_source(other, uri="https://secret.globex.internal/creds", trust=0.9)
    s = eng.add_source(ALICE, uri="mem://a", trust=0.5)
    f = eng.assert_fact(ALICE, subject="X", predicate="p", object="findme", source=s.id)
    # repoint the fact's source at globex's source (models crafted/imported dangling state)
    obj = eng.store.get_object(f.id)
    obj["source"] = secret.id
    eng.store._conn.execute("UPDATE objects SET json=? WHERE id=?", (canonical_json(obj), f.id))
    eng.rebuild_index()

    res = eng.search(ALICE, text="findme", limit=10)
    assert res
    src_view = res[0]["source"]
    assert src_view is None or "secret.globex" not in str(src_view.get("uri", "")), \
        "search leaked a cross-tenant source URI"
    exp = eng.explain(ALICE, f.id)
    sv = exp.get("source") or {}
    assert "secret.globex" not in str(sv.get("uri", "")), "explain leaked a cross-tenant source URI"
    eng.close()


def test_in_scope_source_still_shown(tmp_path) -> None:
    """Anti-regression: an in-scope source is still displayed with its uri and trust."""
    eng = _sqlite_engine(tmp_path)
    s = eng.add_source(ALICE, uri="mem://ok", trust=0.7)
    eng.assert_fact(ALICE, subject="X", predicate="p", object="findme", source=s.id)
    res = eng.search(ALICE, text="findme", limit=10)
    assert res and res[0]["source"] and res[0]["source"]["uri"] == "mem://ok"
    eng.close()
