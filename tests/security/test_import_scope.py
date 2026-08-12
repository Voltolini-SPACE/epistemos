"""EPISTEMOS-03 audit: the LEDGER RECORD HEADER is the sole authority for scope.

Findings A-01 / A-02 (both CRITICAL, EPISTEMOS-03 audit).

The import path projects an event's payload into queryable state. Before this fix the
projection trusted ``payload["tenant"]``/``payload["namespace"]`` — attacker-controlled data —
instead of the sealed record header. A hand-built export whose chain is internally valid could
therefore write objects into *any* tenant's scope, defeating the fail-closed multi-tenant
invariant without breaking a single hash.

Separately, ``import_events(migrate=True)`` re-sealed the incoming events into a fresh chain
without ever verifying the chain it was handed, so the migrate flag silently disabled
tamper-evidence.
"""

from __future__ import annotations

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos._util import canonical_json, sha256_hex
from epistemos.errors import IntegrityError
from epistemos.ledger import GENESIS_HASH, content_hash
from epistemos.storage import SQLiteStore

VICTIM = Principal(tenant="acme", agent="claude", namespace="hr")
ATTACKER = Principal(tenant="attacker", agent="mallory", namespace="ns")


def _engine(tmp_path, name: str) -> Engine:
    return Engine(SQLiteStore(tmp_path / f"{name}.db"), clock=ManualClock())


def _reseal_chain(payload: dict) -> dict:
    """Recompute every hash so the exported chain is internally VALID again."""
    prev = GENESIS_HASH
    for ev in payload["events"]:
        ch = content_hash(ev["op"], ev["payload"])
        header = {
            "seq": ev["seq"], "ts": ev["ts"], "op": ev["op"],
            "tenant": ev["tenant"], "namespace": ev["namespace"],
            "actor": ev["actor"], "principal": ev["principal"],
            "content_hash": ch, "prev_hash": prev,
        }
        entry = sha256_hex(canonical_json(header))
        ev["content_hash"], ev["prev_hash"], ev["entry_hash"] = ch, prev, entry
        prev = entry
    return payload


def _hostile_export(tmp_path) -> dict:
    """An export the attacker fully controls, whose payloads claim the victim's scope."""
    donor = _engine(tmp_path, "donor")
    src = donor.add_source(ATTACKER, uri="mem://evil", trust=1.0)
    donor.assert_fact(ATTACKER, subject="Alice", predicate="salary",
                      object="SMUGGLED", source=src.id)
    payload = donor.export()
    donor.close()
    for ev in payload["events"]:
        if isinstance(ev["payload"], dict) and "tenant" in ev["payload"]:
            ev["payload"]["tenant"] = VICTIM.tenant
            ev["payload"]["namespace"] = VICTIM.namespace
    return _reseal_chain(payload)


def test_import_rejects_payload_scope_mismatch(tmp_path) -> None:
    """A-01: payload scope that disagrees with the sealed header must fail closed."""
    payload = _hostile_export(tmp_path)
    victim = _engine(tmp_path, "victim")
    with pytest.raises(IntegrityError):
        victim.import_events(payload, verify=True)
    # and nothing leaked into the victim's scope
    assert list(victim.store.objects(VICTIM.tenant, VICTIM.namespace)) == []
    victim.close()


def test_import_scope_mismatch_not_searchable(tmp_path) -> None:
    """A-01: the smuggled object must never become retrievable in the victim's scope."""
    payload = _hostile_export(tmp_path)
    victim = _engine(tmp_path, "victim2")
    with pytest.raises(IntegrityError):
        victim.import_events(payload, verify=True)
    assert victim.search(VICTIM, text="SMUGGLED", limit=10) == []
    victim.close()


def test_migrate_import_verifies_incoming_chain(tmp_path) -> None:
    """A-02: migrate=True must not be a way to skip tamper-evidence."""
    donor = _engine(tmp_path, "m_donor")
    src = donor.add_source(VICTIM, uri="mem://s", trust=0.5)
    donor.assert_fact(VICTIM, subject="Alice", predicate="works_at",
                      object="Acme", source=src.id)
    payload = donor.export()
    donor.close()
    payload["schema_version"] = 0  # force the migrate branch
    for ev in payload["events"]:
        if ev["op"] == "fact_asserted":
            ev["payload"]["object"] = "TAMPERED"  # payload no longer matches content_hash

    victim = _engine(tmp_path, "m_victim")
    with pytest.raises(IntegrityError):
        victim.import_events(payload, verify=True, migrate=True)
    assert victim.current(VICTIM, subject="Alice", predicate="works_at") is None
    victim.close()


def test_migrate_import_accepts_genuine_old_export(tmp_path) -> None:
    """A-02 must not break the legitimate migrate path: an untampered old export still imports."""
    donor = _engine(tmp_path, "g_donor")
    src = donor.add_source(VICTIM, uri="mem://s", trust=0.5)
    donor.assert_fact(VICTIM, subject="Alice", predicate="works_at",
                      object="Acme", source=src.id)
    payload = donor.export()
    donor.close()
    # A genuine v0 export: old field names, chain sealed over the OLD payloads.
    payload["schema_version"] = 0
    for ev in payload["events"]:
        p = ev["payload"]
        if p.get("kind") == "fact":
            p["valid_start"] = p.pop("valid_from", None)
            p["valid_end"] = p.pop("valid_to", None)
            p.pop("status", None)
            p["schema_version"] = 0
    _reseal_chain(payload)

    victim = _engine(tmp_path, "g_victim")
    n = victim.import_events(payload, verify=True, migrate=True)
    assert n == len(payload["events"])
    assert victim.current(VICTIM, subject="Alice", predicate="works_at") == "Acme"
    victim.verify_integrity()  # the re-sealed chain is itself valid
    victim.close()


def test_import_verify_false_still_enforces_scope(tmp_path) -> None:
    """A-01: skipping chain verification must NOT also skip the scope check."""
    payload = _hostile_export(tmp_path)
    victim = _engine(tmp_path, "nv_victim")
    with pytest.raises(IntegrityError):
        victim.import_events(payload, verify=False)
    assert list(victim.store.objects(VICTIM.tenant, VICTIM.namespace)) == []
    victim.close()


def test_legitimate_round_trip_still_works(tmp_path) -> None:
    """Anti-regression: an honest export/import round trip is unaffected by the scope check."""
    donor = _engine(tmp_path, "rt_donor")
    src = donor.add_source(VICTIM, uri="mem://s", trust=0.7)
    f = donor.assert_fact(VICTIM, subject="Alice", predicate="works_at",
                          object="Acme", source=src.id)
    donor.supersede(VICTIM, f.id, new=dict(object="Beta"))
    e1 = donor.add_entity(VICTIM, name="E1")
    e2 = donor.add_entity(VICTIM, name="E2")
    donor.merge_entities(VICTIM, canonical=e1.id, duplicates=[e2.id])
    donor.split_entity(VICTIM, e1.id, into=[dict(name="S1")])
    payload = donor.export()
    donor.close()

    victim = _engine(tmp_path, "rt_victim")
    n = victim.import_events(payload, verify=True)
    assert n == payload["event_count"]
    # anchored past the donor clock's window (the victim's ManualClock restarts at the
    # same base, so "now" would sit before the superseding fact's valid_from)
    assert victim.as_of(VICTIM, "2027-01-01", subject="Alice", predicate="works_at") == "Beta"
    assert {o["name"] for o in victim.store.objects(VICTIM.tenant, VICTIM.namespace,
                                                    kind="entity")} == {"E1", "E2", "S1"}
    victim.verify_integrity()
    victim.close()
