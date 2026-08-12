"""EPCTX/1 protocol — spec, serialization, versioning, transport parity, expansion, compat.

Answers the mission's final questions (§45) with executable checks: a generic consumer can read the
document without internals; claim stays distinguishable from fact; contradictions stay explicit;
incompleteness is detectable; provenance stays queryable; temporal state stays clear; local / REST /
MCP deliver equivalent semantics; and the protocol works with no NOMOS/Hermes/OpenClaw in sight.
"""

from __future__ import annotations

import pytest

from epistemos.protocol import build_epctx, canonical_json, context_hash, is_compatible
from epistemos.protocol.serialize import HASH_ALGO
from epistemos.protocol.versioning import (
    REQUIRED_TOP_LEVEL,
    assert_required,
    parse_version,
)

from .conftest import clients, seed


# ---- spec / shape ---------------------------------------------------------
def test_required_fields_present(seeded):
    engine, alice, _ = seeded
    doc = engine.epctx(alice, "Datastore", intent="current")
    assert doc["protocol_version"] == "EPCTX/1"
    for field in REQUIRED_TOP_LEVEL:
        assert field in doc, field
    assert_required(doc)  # producer self-check must pass


def test_context_is_sectioned_by_type(seeded):
    engine, alice, _ = seeded
    doc = engine.epctx(alice, "Adopt Postgres", intent="decision")
    assert set(doc["context"]) == {"facts", "claims", "evidence", "reviews", "decisions", "sources"}


def test_claim_is_distinguishable_from_fact(seeded):
    engine, alice, _ = seeded
    fdoc = engine.epctx(alice, "Datastore", intent="current")
    cdoc = engine.epctx(alice, "Revenue", intent="current")
    fact = fdoc["context"]["facts"][0]
    claim = cdoc["context"]["claims"][0]
    assert fact["object_type"] == "fact" and fact["belief_state"] == "asserted"
    assert claim["object_type"] == "claim"
    assert claim["belief_state"] in ("proposed", "supported", "disputed", "accepted", "open")
    assert claim["accepted_state"] is False           # a bare disputed claim is NOT accepted fact


def test_contradictions_are_a_separate_section(seeded):
    engine, alice, ids = seeded
    doc = engine.epctx(alice, "Revenue", intent="contradiction")
    assert doc["disputed"] is True
    assert any(c["id"] == ids["contra"] for c in doc["contradictions"])
    # the contradicting evidence must NOT also appear under supporting evidence
    assert ids["contra"] not in [e["id"] for e in doc["context"]["evidence"]]


def test_completeness_is_declared(seeded):
    engine, alice, _ = seeded
    cur = engine.epctx(alice, "Datastore", intent="current")     # collapses history
    hist = engine.epctx(alice, "Datastore", intent="historical")  # preserves history
    assert cur["completeness"]["complete"] is False
    assert "history_collapsed" in cur["completeness"]["reasons"]
    assert hist["completeness"]["complete"] is True


def test_temporal_contract(seeded):
    engine, alice, _ = seeded
    hist = engine.epctx(alice, "Datastore", intent="historical")
    assert hist["temporal"]["has_current_state"] and hist["temporal"]["has_historical_state"]
    facts = hist["context"]["facts"]
    assert any(f["temporal"]["is_current"] for f in facts)
    assert any(not f["temporal"]["is_current"] for f in facts)


def test_provenance_is_queryable(seeded):
    engine, alice, _ = seeded
    doc = engine.epctx(alice, "Adopt Postgres", intent="decision")
    rows = doc["provenance"]["items"]
    dec = next(r for r in rows if r["object_type"] == "decision")
    assert dec["evidence_refs"], "decision must expose its supporting evidence refs"


def test_token_accounting(seeded):
    engine, alice, _ = seeded
    doc = engine.epctx(alice, "Datastore", intent="historical")
    assert doc["tokenizer_profile"]
    assert isinstance(doc["token_estimate"], int)
    assert set(doc["tokens_by_section"]) >= set(doc["context"])


# ---- serialization / integrity (§5, §6) -----------------------------------
def test_canonical_serialization_is_deterministic():
    a = {"b": 1, "a": [3, 2, 1], "c": {"y": 2, "x": 1}}
    b = {"c": {"x": 1, "y": 2}, "a": [3, 2, 1], "b": 1}
    assert canonical_json(a) == canonical_json(b)  # same logical value -> same bytes


def test_integrity_hash_self_consistent(seeded):
    engine, alice, _ = seeded
    doc = engine.epctx(alice, "Datastore", intent="current")
    assert doc["integrity"]["algo"] == HASH_ALGO
    assert context_hash(doc) == doc["integrity"]["context_hash"]


def test_integrity_detects_tampering(seeded):
    engine, alice, _ = seeded
    doc = engine.epctx(alice, "Datastore", intent="current")
    original = doc["integrity"]["context_hash"]
    doc["context"]["facts"].append({"id": "spoof", "text": "injected", "object_type": "fact"})
    assert context_hash(doc) != original  # any alteration changes the hash


# ---- versioning (§4) ------------------------------------------------------
def test_version_parsing_and_compat():
    assert parse_version("EPCTX/1") == (1, 0)
    assert parse_version("EPCTX/1.4") == (1, 4)
    assert is_compatible("EPCTX/1") and is_compatible("EPCTX/1.9")
    assert not is_compatible("EPCTX/2")
    assert not is_compatible("garbage")


def test_unknown_optional_field_is_ignored_by_required_check(seeded):
    engine, alice, _ = seeded
    doc = engine.epctx(alice, "Datastore", intent="current")
    doc["some_future_optional"] = {"whatever": True}   # a newer minor added a field
    assert_required(doc)   # a conservative consumer still validates; unknown field is tolerated


# ---- transport parity (§13, §44) ------------------------------------------
@pytest.mark.parametrize("query,intent", [
    ("Datastore", "current"), ("Datastore", "historical"), ("Revenue", "contradiction"),
    ("Adopt Postgres", "decision"),
])
def test_local_rest_mcp_equivalent(engine, alice, rest_server, query, intent):
    cs = clients(engine, alice, rest_server)

    def semantics(d):
        return (
            d["protocol_version"], d["disputed"],
            {k: len(v) for k, v in d["context"].items()},
            d["completeness"],
            (d["temporal"]["has_current_state"], d["temporal"]["has_historical_state"]),
            sorted(c["id"] for c in d["contradictions"]),
        )

    got = {name: semantics(c.context(query, intent=intent)) for name, c in cs.items()}
    assert got["local"] == got["rest"] == got["mcp"], got


# ---- expansion (§21) ------------------------------------------------------
def test_expansion_roundtrip_local(seeded):
    engine, alice, _ = seeded
    doc = engine.epctx(alice, "Datastore", intent="current")
    assert doc["expansion"]["available"]
    handle = doc["expansion"]["handles"][0]["handle"]
    out = engine.expand(alice, handle)
    assert out["authorized"] is True
    assert out["members"], "expansion must return the collapsed members for the owner"


def test_expansion_parity_across_transports(engine, alice, rest_server):
    seed(engine, alice)
    cs = clients(engine, alice, rest_server)
    for name, c in cs.items():
        doc = c.context("Datastore", intent="current")
        handle = doc["expansion"]["handles"][0]["handle"]
        out = c.expand(handle)
        assert out["authorized"] and out["members"], name


# ---- backward compatibility (§33) -----------------------------------------
def test_search_and_context_unchanged(seeded):
    engine, alice, _ = seeded
    # engine.search still returns raw hits; engine.context still returns the v0.6 envelope view
    assert isinstance(engine.search(alice, text="Datastore"), list)
    v06 = engine.context(alice, "Datastore", intent="current")
    assert v06["format"] == "EPCTX/1" and "items" in v06


def test_build_epctx_is_pure_function_of_state(seeded):
    engine, alice, _ = seeded
    a = build_epctx(engine, alice, query="Datastore", intent="historical")
    b = build_epctx(engine, alice, query="Datastore", intent="historical")
    # identical inputs -> identical document EXCEPT freshly-minted expansion handles
    a["expansion"] = b["expansion"] = {}
    a["integrity"] = b["integrity"] = {}
    assert canonical_json(a) == canonical_json(b)


def test_works_without_any_consumer_framework(seeded):
    # No NOMOS / Hermes / OpenClaw imported anywhere in this module or its deps (§10 of §45).
    import sys
    engine, alice, _ = seeded
    engine.epctx(alice, "Datastore", intent="current")
    assert not any(m.startswith(("nomos", "hermes", "openclaw")) for m in sys.modules)
