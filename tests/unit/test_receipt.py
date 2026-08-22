"""Retrieval receipts: what they must prove, and what they must refuse to prove.

The receipt exists to answer "what did the agent actually see?" after the store has moved on. Its
value is entirely in being unforgeable and deterministic — a receipt that changes between identical
runs, or that still verifies after an edit, proves nothing at all.
"""

from __future__ import annotations

import dataclasses

import pytest

from epistemos import Engine, Principal, ReceiptChain, RetrievalReceipt
from epistemos.errors import IntegrityError
from epistemos.receipt import RECEIPT_VERSION

TEXT = "Owner: Alice Martins\nAlice Martins works at Acme.\nTier: critical\n"


def _seed(engine, ctx, n=3):
    for i in range(n):
        engine.ingest_document(ctx, title=f"Runbook {i}", text=TEXT.replace("critical", f"t{i}"))


# -- what the receipt proves -------------------------------------------------


def test_receipt_seals_the_query_without_storing_it(engine, ctx):
    """The query text is not sealed verbatim — a hash is. A receipt should be shareable as
    evidence without disclosing what someone searched for."""
    _seed(engine, ctx)
    _res, receipt = engine.search_sealed(ctx, text="Alice Martins")

    assert receipt.matches_query("Alice Martins")
    assert not receipt.matches_query("Alice Martin")
    assert "Alice" not in str(receipt.to_dict())


def test_receipt_records_the_ranking_inputs_and_the_ranking(engine, ctx):
    _seed(engine, ctx)
    results, receipt = engine.search_sealed(ctx, text="Alice")

    assert receipt.scorer_version
    assert receipt.projection_version == engine.store.event_count()
    assert set(receipt.weights) >= {"lexical", "exact", "recency"}
    assert [r["rank"] for r in receipt.results] == list(range(1, len(results) + 1))
    for sealed, live in zip(receipt.results, results, strict=True):
        assert sealed["id"] == live["id"]
        assert sealed["score"] == pytest.approx(live["score"])
        # "why was this ranked here" must be answerable from the receipt alone.
        assert sealed["score_components"]
        assert sealed["why_returned"]


def test_receipt_verifies_and_survives_a_round_trip(engine, ctx):
    _seed(engine, ctx)
    _res, receipt = engine.search_sealed(ctx, text="Alice")
    assert receipt.verify()

    restored = RetrievalReceipt.from_dict(receipt.to_dict())
    assert restored.verify()
    assert restored.receipt_hash == receipt.receipt_hash


# -- determinism -------------------------------------------------------------


def test_same_query_same_projection_seals_to_the_same_bytes(engine, ctx):
    """Wall-clock time is deliberately outside the digest; otherwise nothing would ever replay."""
    _seed(engine, ctx)
    hashes = {engine.search_sealed(ctx, text="Alice")[1].receipt_hash for _ in range(5)}
    assert len(hashes) == 1


def test_execution_metadata_is_outside_the_digest(engine, ctx):
    _seed(engine, ctx)
    _res, receipt = engine.search_sealed(ctx, text="Alice")
    assert "started_at" in receipt.execution
    assert "started_at" not in receipt.payload()
    tampered = dataclasses.replace(receipt, execution={"started_at": "1999-01-01T00:00:00Z"})
    assert tampered.verify()  # editing execution metadata does not invalidate the seal


def test_a_changed_projection_changes_the_receipt(engine, ctx):
    _seed(engine, ctx)
    first = engine.search_sealed(ctx, text="Alice")[1]
    engine.ingest_document(ctx, title="another", text=TEXT)
    second = engine.search_sealed(ctx, text="Alice")[1]
    assert second.projection_version > first.projection_version
    assert second.receipt_hash != first.receipt_hash


# -- tamper detection --------------------------------------------------------


@pytest.mark.parametrize("field,value", [
    ("tenant", "evil"),
    ("namespace", "other"),
    ("agent", "mallory"),
    ("query_hash", "0" * 64),
    ("projection_version", 999),
    ("scorer_version", "fake/9"),
])
def test_editing_any_sealed_field_breaks_verification(engine, ctx, field, value):
    _seed(engine, ctx)
    _res, receipt = engine.search_sealed(ctx, text="Alice")
    assert dataclasses.replace(receipt, **{field: value}).verify() is False


def test_editing_a_score_breaks_verification(engine, ctx):
    _seed(engine, ctx)
    _res, receipt = engine.search_sealed(ctx, text="Alice")
    forged = dataclasses.replace(
        receipt, results=tuple([{**receipt.results[0], "score": 9.99}, *receipt.results[1:]])
    )
    assert forged.verify() is False


def test_reordering_results_breaks_verification(engine, ctx):
    """Rank is part of the claim. Re-ordering is falsification, not presentation."""
    _seed(engine, ctx, n=4)
    _res, receipt = engine.search_sealed(ctx, text="Alice")
    if len(receipt.results) < 2:
        pytest.skip("needs at least two results")
    swapped = dataclasses.replace(
        receipt, results=tuple([receipt.results[1], receipt.results[0], *receipt.results[2:]])
    )
    assert swapped.verify() is False


def test_dropping_a_result_breaks_verification(engine, ctx):
    _seed(engine, ctx, n=4)
    _res, receipt = engine.search_sealed(ctx, text="Alice")
    if len(receipt.results) < 2:
        pytest.skip("needs at least two results")
    truncated = dataclasses.replace(receipt, results=receipt.results[:-1])
    assert truncated.verify() is False


def test_an_unknown_receipt_version_is_refused_not_guessed(engine, ctx):
    _seed(engine, ctx)
    d = engine.search_sealed(ctx, text="Alice")[1].to_dict()
    d["receipt_version"] = RECEIPT_VERSION + 1
    with pytest.raises(IntegrityError):
        RetrievalReceipt.from_dict(d)


# -- signatures --------------------------------------------------------------


def test_hmac_binds_the_receipt_to_a_key(engine, ctx):
    _seed(engine, ctx)
    _res, receipt = engine.search_sealed(ctx, text="Alice", secret=b"correct-key")
    assert receipt.verify(secret=b"correct-key")
    assert receipt.verify(secret=b"wrong-key") is False
    # Still tamper-evident without the key, just not attributable.
    assert receipt.verify()


def test_an_unsigned_receipt_never_passes_a_signed_check(engine, ctx):
    _seed(engine, ctx)
    _res, receipt = engine.search_sealed(ctx, text="Alice")
    assert receipt.signature is None
    assert receipt.verify(secret=b"any") is False


# -- chaining ----------------------------------------------------------------


def test_a_chain_detects_a_removed_receipt(engine, ctx):
    """An individually valid receipt says nothing about receipts that were deleted around it."""
    _seed(engine, ctx)
    chain, prev = ReceiptChain(), None
    for q in ("Alice", "Acme", "Runbook", "critical"):
        _res, r = engine.search_sealed(ctx, text=q, previous=prev)
        chain.append(r)
        prev = r
    assert chain.verify() == 4

    chain.receipts.pop(1)
    with pytest.raises(IntegrityError, match="chain broken"):
        chain.verify()


def test_a_receipt_that_does_not_link_is_refused_on_append(engine, ctx):
    _seed(engine, ctx)
    chain = ReceiptChain()
    _res, first = engine.search_sealed(ctx, text="Alice")
    chain.append(first)
    _res, orphan = engine.search_sealed(ctx, text="Acme")  # previous=None, does not link
    with pytest.raises(IntegrityError, match="does not link"):
        chain.append(orphan)


# -- isolation ---------------------------------------------------------------


def test_a_receipt_is_scoped_to_the_principal_that_produced_it(store):
    """Two tenants issuing the identical query against identical text must not produce the same
    receipt — otherwise a receipt would be evidence about someone else's data."""
    engine = Engine(store)
    a = Principal(tenant="acme", agent="x", namespace="kb")
    b = Principal(tenant="globex", agent="x", namespace="kb")
    engine.ingest_document(a, title="Runbook", text=TEXT)
    engine.ingest_document(b, title="Runbook", text=TEXT)

    _ra, ra = engine.search_sealed(a, text="Alice Martins")
    _rb, rb = engine.search_sealed(b, text="Alice Martins")

    assert ra.query_hash == rb.query_hash        # same question
    assert ra.receipt_hash != rb.receipt_hash    # different answer, different seal
    assert ra.tenant == "acme"
    sealed_ids = {r["id"] for r in ra.results}
    for r in rb.results:
        assert r["id"] not in sealed_ids


def test_an_empty_result_still_seals(engine, ctx):
    """A retrieval that found nothing is a fact worth proving — 'we looked and there was nothing'
    is exactly the kind of claim that gets disputed later."""
    _seed(engine, ctx)
    results, receipt = engine.search_sealed(ctx, text="zzz-no-such-term-zzz")
    assert results == []
    assert receipt.results == ()
    assert receipt.verify()
    assert receipt.execution["result_count"] == 0
