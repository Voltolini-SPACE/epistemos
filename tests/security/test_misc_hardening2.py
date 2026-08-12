"""EPISTEMOS-03 audit: second robustness batch.

T-07 (timeline chronological order), T-08 (naive datetime on a public helper), B-06 isolation
(metadata cap not re-checked on cross-agent append), LT-05 (backup deadlock inside a txn),
B-05 boundaries (REST does not drain an unconsumed body -> request smuggling).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal
from epistemos.errors import StorageError
from epistemos.storage import MemoryStore, SQLiteStore
from epistemos.temporal import instant_in_interval

CTX = Principal(tenant="acme", agent="a", namespace="hr")
BOB = Principal(tenant="acme", agent="bob", namespace="hr")


def test_timeline_is_chronological_across_offset_forms() -> None:
    """T-07: timeline must order by real instant, not lexicographically over offset strings."""
    eng = Engine(MemoryStore(), clock=ManualClock())
    s = eng.add_source(CTX, uri="mem://s", trust=0.9)
    # same instant, three textual forms; plus an earlier and a later one
    eng.assert_fact(CTX, subject="X", predicate="p", object="a",
                    valid_from="2026-01-01T12:00:00+05:00", source=s.id)
    eng.assert_fact(CTX, subject="X", predicate="p", object="b",
                    valid_from="2026-01-01T00:00:00Z", source=s.id)
    eng.assert_fact(CTX, subject="X", predicate="p", object="c",
                    valid_from="2026-06-01T00:00:00Z", source=s.id)
    tl = eng.timeline(CTX, subject="X")
    from epistemos._util import parse_instant
    valids = [parse_instant(r["valid_from"]) for r in tl if r["valid_from"]]
    # within the same tx ordering the validity axis must be non-decreasing by true instant
    tx_order = [(r["tx_from"], parse_instant(r["valid_from"])) for r in tl if r["valid_from"]]
    for (t1, v1), (t2, v2) in zip(tx_order, tx_order[1:], strict=False):
        if t1 == t2:
            assert v1 <= v2, "timeline mis-ordered mixed-offset validity within one tx instant"
    assert valids  # sanity


def test_instant_in_interval_accepts_naive_datetime() -> None:
    """T-08: the public helper must treat a naive datetime as UTC, like valid_at/believed_at."""
    naive = datetime(2026, 1, 15)  # no tzinfo
    assert instant_in_interval(naive, "2026-01-01", "2026-02-01") is True
    assert instant_in_interval(naive, "2026-02-01", None) is False


def test_metadata_cap_reenforced_on_cross_agent_append() -> None:
    """B-06 isolation: confirm/contradict append to metadata; the size cap must still hold."""
    eng = Engine(MemoryStore(), clock=ManualClock())
    s = eng.add_source(CTX, uri="mem://s", trust=0.9)
    f = eng.assert_fact(CTX, subject="X", predicate="p", object="v", source=s.id)
    # pre-fill metadata close to the 64 KiB cap by asserting with large metadata is capped on
    # create; here we drive many confirms and assert the object never exceeds the cap.
    sb = eng.add_source(BOB, uri="mem://b", trust=0.9)
    from epistemos.core import _MAX_ANNOTATIONS
    for _ in range(_MAX_ANNOTATIONS + 200):
        eng.confirm(BOB, f.id, source=sb.id, delta_confidence=0.0)
    from epistemos._util import canonical_json
    obj = eng.store.get_object(f.id)
    corr = obj.get("metadata", {}).get("corroborations", [])
    assert len(corr) <= _MAX_ANNOTATIONS, "corroboration list grew without bound"
    size = len(canonical_json(obj.get("metadata", {})).encode("utf-8"))
    assert size <= eng.limits.max_metadata_bytes


def test_backup_inside_transaction_fails_fast(tmp_path) -> None:
    """LT-05: backup() called while the store's own transaction is open must not deadlock."""
    eng = Engine(SQLiteStore(tmp_path / "b.db"), clock=ManualClock())
    s = eng.add_source(CTX, uri="mem://s", trust=0.9)
    eng.assert_fact(CTX, subject="X", predicate="p", object="v", source=s.id)
    with eng.store.atomic(), pytest.raises(StorageError):
        eng.store.backup(str(tmp_path / "snap.db"))
    # a normal backup (no open txn) still works
    eng.store.backup(str(tmp_path / "snap2.db"))
    eng.close()


def test_rest_drains_body_on_error(tmp_path) -> None:
    """B-05 boundaries: an error response must consume the request body (no pipelining smuggle)."""
    import http.client
    import threading

    from epistemos.api.rest import make_server

    eng = Engine(SQLiteStore(tmp_path / "r.db"), clock=ManualClock())
    srv = make_server(eng, tokens={"tok": CTX})
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        # a bad token (401) with a large body: the server must read the body so the connection
        # stays framed and a following request on the same connection is answered correctly.
        conn.request("POST", "/facts", body=b"x" * 100000,
                     headers={"Authorization": "Bearer wrong", "Content-Type": "application/json"})
        r1 = conn.getresponse()
        assert r1.status == 401
        r1.read()
        # reuse the connection: a valid health call must be answered, not desynced
        conn.request("GET", "/health", headers={"Authorization": "Bearer tok"})
        r2 = conn.getresponse()
        assert r2.status == 200
        r2.read()
        conn.close()
    finally:
        srv.shutdown()
        srv.server_close()
