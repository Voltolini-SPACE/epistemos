"""LEDGER_TAMPER_EVIDENCE gate (checkpoint G).

Each attack on the hash chain must be detected. We are precise about the crypto: a bare
hash chain is tamper-evident but tail-truncation / full re-chain need an external anchor
(expected_count/expected_head), which we also test.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from epistemos.errors import IntegrityError
from epistemos.ledger import GENESIS_HASH, Event, seal, verify_chain


def build_chain(n: int = 4) -> list:
    recs = []
    prev = GENESIS_HASH
    for i in range(1, n + 1):
        ev = Event(op="fact_asserted", ts=f"2026-01-0{i}T00:00:00Z", tenant="t",
                   namespace="ns", actor="a", principal=None, payload={"id": f"x{i}", "v": i})
        r = seal(seq=i, event=ev, prev_hash=prev)
        recs.append(r)
        prev = r.entry_hash
    return recs


def test_valid_chain_verifies() -> None:
    recs = build_chain()
    assert verify_chain(recs) == 4
    assert verify_chain(recs, expected_count=4, expected_head=recs[-1].entry_hash) == 4


def test_edit_payload_detected() -> None:
    recs = build_chain()
    recs[1] = replace(recs[1], payload={"id": "x2", "v": 999})
    with pytest.raises(IntegrityError, match="payload tampered"):
        verify_chain(recs)


def test_edit_tenant_detected() -> None:
    recs = build_chain()
    recs[2] = replace(recs[2], tenant="evil")
    with pytest.raises(IntegrityError, match="header tampered"):
        verify_chain(recs)


def test_edit_timestamp_detected() -> None:
    recs = build_chain()
    recs[2] = replace(recs[2], ts="1999-01-01T00:00:00Z")
    with pytest.raises(IntegrityError, match="header tampered"):
        verify_chain(recs)


def test_remove_middle_detected() -> None:
    recs = build_chain()
    del recs[2]
    with pytest.raises(IntegrityError, match="seq gap"):
        verify_chain(recs)


def test_reorder_detected() -> None:
    recs = build_chain()
    recs[1], recs[2] = recs[2], recs[1]
    with pytest.raises(IntegrityError, match="seq gap"):
        verify_chain(recs)


def test_duplicate_detected() -> None:
    recs = build_chain()
    recs.insert(2, recs[1])
    with pytest.raises(IntegrityError, match="seq gap"):
        verify_chain(recs)


def test_swap_prev_hash_detected() -> None:
    recs = build_chain()
    recs[2] = replace(recs[2], prev_hash=GENESIS_HASH)
    with pytest.raises(IntegrityError, match="chain break"):
        verify_chain(recs)


def test_forged_insert_without_rechain_detected() -> None:
    recs = build_chain()
    forged = replace(recs[1], seq=2, payload={"id": "forged", "v": 42})
    recs.insert(1, forged)
    # seq numbers now collide -> gap detected
    with pytest.raises(IntegrityError):
        verify_chain(recs)


def test_tail_truncation_needs_anchor() -> None:
    recs = build_chain()
    truncated = recs[:2]
    # A shorter valid prefix verifies on its own (documented limitation) ...
    assert verify_chain(truncated) == 2
    # ... but the external anchor catches it.
    with pytest.raises(IntegrityError, match="length mismatch"):
        verify_chain(truncated, expected_count=4)
    with pytest.raises(IntegrityError, match="head mismatch"):
        verify_chain(truncated, expected_head=recs[-1].entry_hash)


def test_full_rechain_rewrite_needs_head_anchor() -> None:
    # Attacker rewrites history AND re-chains it consistently.
    recs = build_chain()
    original_head = recs[-1].entry_hash
    rewritten = []
    prev = GENESIS_HASH
    for i in range(1, 5):
        ev = Event(op="fact_asserted", ts=f"2026-02-0{i}T00:00:00Z", tenant="t",
                   namespace="ns", actor="attacker", principal=None,
                   payload={"id": f"x{i}", "v": i * 100})
        r = seal(seq=i, event=ev, prev_hash=prev)
        rewritten.append(r)
        prev = r.entry_hash
    # Internally consistent -> passes bare verification (honest limitation).
    assert verify_chain(rewritten) == 4
    # The pinned head detects the rewrite.
    with pytest.raises(IntegrityError, match="head mismatch"):
        verify_chain(rewritten, expected_head=original_head)
