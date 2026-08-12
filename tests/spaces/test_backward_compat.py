"""EPISTEMOS-04: v0.3 bases stay valid; legacy knowledge migrates to PRIVATE, never PUBLIC (§34)."""

from __future__ import annotations

from tests.conftest import ManualClock
from tests.spaces.conftest import principal

from epistemos import Engine, Principal
from epistemos.storage import SQLiteStore


def _v03_shaped_export(alice: Principal) -> dict:
    """An export whose object payloads have NO `spaces` field — a pre-EPISTEMOS-04 database."""
    from epistemos._util import canonical_json, sha256_hex
    from epistemos.ledger import GENESIS_HASH, content_hash
    from epistemos.storage import MemoryStore

    eng = Engine(MemoryStore())
    sa = eng.add_source(alice, uri="mem://a", trust=0.9)
    eng.assert_fact(alice, subject="Legacy", predicate="is", object="secretv03", source=sa.id)
    dump = eng.export()
    eng.close()
    # strip the `spaces` field from every payload to simulate v0.3 data
    for ev in dump["events"]:
        if isinstance(ev["payload"], dict):
            ev["payload"].pop("spaces", None)
    prev = GENESIS_HASH
    for ev in dump["events"]:
        ch = content_hash(ev["op"], ev["payload"])
        header = {"seq": ev["seq"], "ts": ev["ts"], "op": ev["op"], "tenant": ev["tenant"],
                  "namespace": ev["namespace"], "actor": ev["actor"],
                  "principal": ev["principal"], "content_hash": ch, "prev_hash": prev}
        eh = sha256_hex(canonical_json(header))
        ev["content_hash"], ev["prev_hash"], ev["entry_hash"] = ch, prev, eh
        prev = eh
    return dump


def test_v03_data_imports_and_is_private(tmp_path) -> None:
    alice = principal("alice")
    dump = _v03_shaped_export(alice)
    eng = Engine(SQLiteStore(tmp_path / "t.db"), clock=ManualClock())
    eng.import_events(dump, verify=True)
    eng.verify_integrity()
    # legacy object has no `spaces` -> PRIVATE to its owner (never public)
    fid = next(o["id"] for o in eng.store.objects("acme", "hr", kind="fact"))
    assert eng.get(alice, fid).object == "secretv03"     # owner still reads
    bob = principal("bob")
    assert eng.get(bob, fid) is None                     # a namespace-mate cannot (private)
    assert eng.search(bob, text="secretv03") == []
    eng.close()


def test_v03_single_agent_behaviour_unchanged(tmp_path) -> None:
    """The overwhelming common case: one agent, everything readable to itself, exactly as v0.3."""
    ctx = principal("solo")
    eng = Engine(SQLiteStore(tmp_path / "s.db"), clock=ManualClock())
    s = eng.add_source(ctx, uri="mem://s", trust=0.9)
    f = eng.assert_fact(ctx, subject="A", predicate="p", object="X", source=s.id)
    eng.end_fact(ctx, f.id, valid_to="2026-02-01")
    eng.assert_fact(ctx, subject="A", predicate="p", object="Y", valid_from="2026-02-01",
                    source=s.id)
    assert eng.current(ctx, subject="A", predicate="p") == "Y"
    assert eng.as_of(ctx, "2026-01-15", subject="A", predicate="p") == "X"
    assert len(eng.search(ctx, text="A", limit=10)) >= 1
    eng.close()
