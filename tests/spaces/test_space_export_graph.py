"""EPISTEMOS-04: export/import space safety (§18) and graph space isolation (§19)."""

from __future__ import annotations

import pytest
from tests.conftest import ManualClock
from tests.spaces.conftest import principal

from epistemos import Engine, Principal
from epistemos._util import canonical_json
from epistemos.errors import NotFoundError
from epistemos.identity import _DEFAULT_CAPS
from epistemos.storage import SQLiteStore

SECRET = "EXPORTSECRET99"


# ---- export / import -------------------------------------------------------
def test_scoped_export_excludes_unreadable_objects(sengine: Engine, alice, bob) -> None:
    """§18: a namespace-mate's scoped export must not contain another agent's private objects."""
    sa = sengine.add_source(alice, uri="mem://a", trust=0.9)
    sengine.assert_fact(alice, subject="Salary", predicate="is", object=SECRET, source=sa.id)
    sb = sengine.add_source(bob, uri="mem://b", trust=0.9)
    sengine.assert_fact(bob, subject="Bob", predicate="role", object="eng", source=sb.id)
    dump = sengine.export(bob)  # bob exports his scope
    blob = canonical_json(dump)
    assert SECRET not in blob, "scoped export leaked another agent's private fact"
    assert "eng" in blob  # bob's own data is present


def test_scoped_export_is_importable_and_selfconsistent(tmp_path, alice, bob) -> None:
    eng = Engine(SQLiteStore(tmp_path / "s.db"), clock=ManualClock())
    sb = eng.add_source(bob, uri="mem://b", trust=0.9)
    eng.assert_fact(bob, subject="Bob", predicate="role", object="engineer", source=sb.id)
    dump = eng.export(bob)
    target = Engine(SQLiteStore(tmp_path / "t.db"), clock=ManualClock())
    n = target.import_events(dump, verify=True)
    assert n == dump["event_count"]
    target.verify_integrity()
    assert target.as_of(bob, "2027-01-01", subject="Bob", predicate="role") == "engineer"
    eng.close()
    target.close()


def test_import_into_empty_store_does_not_grant_foreign_space(tmp_path, alice) -> None:
    """§18: a crafted placement into a non-existent space is dangling -> fail closed (private)."""
    donor = Engine(SQLiteStore(tmp_path / "d.db"), clock=ManualClock())
    sa = donor.add_source(alice, uri="mem://a", trust=0.9)
    f = donor.assert_fact(alice, subject="S", predicate="p", object=SECRET, source=sa.id)
    dump = donor.export(alice)
    donor.close()
    # tamper: claim the fact is placed in a fabricated PUBLIC space id
    for ev in dump["events"]:
        if ev["op"] == "fact_asserted":
            ev["payload"]["spaces"] = ["spc_fabricated_public"]
    # reseal so the chain is internally valid
    from epistemos._util import sha256_hex
    from epistemos.ledger import GENESIS_HASH, content_hash
    prev = GENESIS_HASH
    for ev in dump["events"]:
        ch = content_hash(ev["op"], ev["payload"])
        header = {"seq": ev["seq"], "ts": ev["ts"], "op": ev["op"], "tenant": ev["tenant"],
                  "namespace": ev["namespace"], "actor": ev["actor"],
                  "principal": ev["principal"], "content_hash": ch, "prev_hash": prev}
        eh = sha256_hex(canonical_json(header))
        ev["content_hash"], ev["prev_hash"], ev["entry_hash"] = ch, prev, eh
        prev = eh
    target = Engine(SQLiteStore(tmp_path / "t.db"), clock=ManualClock())
    target.import_events(dump, verify=True)
    # the fabricated space does not exist -> the placement grants nobody access.
    bob = principal("bob")
    assert target.search(bob, text=SECRET) == []
    assert target.get(bob, f.id) is None
    target.close()


# ---- graph space isolation -------------------------------------------------
def test_graph_traversal_does_not_leak_private_node(sengine: Engine, alice, bob) -> None:
    """§19: a PUBLIC node linked by a PRIVATE edge to a PRIVATE node must not reveal that node."""
    # alice builds: pub_entity --(private rel)--> secret_entity
    pub = sengine.add_entity(alice, name="PublicCo")
    secret = sengine.add_entity(alice, name="SecretSub" + SECRET)
    sengine.add_relation(alice, source_entity=pub.id, target_entity=secret.id, rel_type="owns")
    # alice shares ONLY the public entity into a team space bob is in
    space = sengine.create_space(alice, name="team", visibility="TEAM")
    sengine.grant_capability(alice, space_id=space.id, agent="bob")
    sengine.share(alice, pub.id, into=space.id)
    # bob can read the public entity, but neighbors must not expose the private edge/node
    assert sengine.get(bob, pub.id).name == "PublicCo"
    nbrs = sengine.neighbors(bob, pub.id)
    blob = canonical_json(nbrs)
    assert SECRET not in blob and secret.id not in blob, "graph leaked a private neighbour"
    assert nbrs == []  # the only edge points to a node bob cannot read
    # and bob cannot traverse into the private node directly
    with pytest.raises(NotFoundError):
        sengine.neighbors(bob, secret.id)


def test_graph_edge_visible_when_both_endpoints_shared(sengine: Engine, alice, bob) -> None:
    a = sengine.add_entity(alice, name="A")
    b = sengine.add_entity(alice, name="B")
    rel = sengine.add_relation(alice, source_entity=a.id, target_entity=b.id, rel_type="links")
    space = sengine.create_space(alice, name="team", visibility="TEAM")
    sengine.grant_capability(alice, space_id=space.id, agent="bob")
    for oid in (a.id, b.id, rel.id):
        sengine.share(alice, oid, into=space.id)
    nbrs = sengine.neighbors(bob, a.id)
    assert len(nbrs) == 1 and nbrs[0]["target_entity"] == b.id


def test_org_promoted_knowledge_is_tenant_wide(sengine: Engine, alice) -> None:
    """A fact promoted to ORGANIZATION is readable by any agent in the tenant."""
    sa = sengine.add_source(alice, uri="mem://a", trust=0.9)
    f = sengine.assert_fact(alice, subject="Policy", predicate="is", object="open", source=sa.id)
    org = sengine.create_space(alice, name="org", visibility="ORGANIZATION")
    promoter = Principal(tenant="acme", agent="alice", namespace="hr",
                         capabilities=_DEFAULT_CAPS | {"knowledge.promote"})
    sengine.promote(promoter, f.id, into=org.id)
    # a brand-new agent in the tenant (never granted) can read org knowledge
    newcomer = principal("carol")
    assert sengine.get(newcomer, f.id).object == "open"
    assert sengine.current(newcomer, subject="Policy", predicate="is") == "open"
