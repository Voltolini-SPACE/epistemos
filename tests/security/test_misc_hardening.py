"""EPISTEMOS-03 audit: assorted robustness/correctness findings.

OV-08 (version), LT-04 (recall order determinism), OV-03 (locked DB misdiagnosed as
FTS5-absent), B-04 boundaries (REST drops derived_from/memory_class), B-08 (limit not
validated), B-05 index (kinds type confusion).
"""

from __future__ import annotations

import pytest
from tests.conftest import ManualClock

from epistemos import Engine, Principal, __version__
from epistemos.errors import ValidationError
from epistemos.storage import MemoryStore, SQLiteStore

CTX = Principal(tenant="acme", agent="a", namespace="hr")


def test_package_version_is_current() -> None:
    """OV-08: the shipped version must not still claim 0.1.0."""
    assert __version__ == "0.3.0"


def test_recall_order_is_deterministic_across_backends(tmp_path) -> None:
    """LT-04: recall(limit=n) must return the same objects regardless of backend/iteration order."""
    def build(store):
        e = Engine(store, clock=ManualClock())
        s = e.add_source(CTX, uri="mem://s", trust=0.9)
        for i in range(20):
            e.assert_fact(CTX, subject=f"S{i}", predicate="p", object=f"v{i}", source=s.id)
        return e
    mem = build(MemoryStore())
    sql = build(SQLiteStore(tmp_path / "r.db"))
    # same created_at ordering; ties broken deterministically -> identical top-k statements
    mk = [(o.get("subject"), o.get("object")) for o in mem.recall(CTX, limit=10)]
    sk = [(o.get("subject"), o.get("object")) for o in sql.recall(CTX, limit=10)]
    assert mk == sk
    sql.close()


def test_search_limit_is_validated(tmp_path) -> None:
    """B-08: a negative limit must be rejected, not silently slice all-but-one."""
    e = Engine(SQLiteStore(tmp_path / "l.db"), clock=ManualClock())
    s = e.add_source(CTX, uri="mem://s", trust=0.9)
    for i in range(5):
        e.assert_fact(CTX, subject=f"S{i}", predicate="p", object="findme", source=s.id)
    with pytest.raises(ValidationError):
        e.search(CTX, text="findme", limit=-1)
    assert len(e.search(CTX, text="findme", limit=3)) == 3
    e.close()


def test_kinds_must_be_a_tuple_of_strings(tmp_path) -> None:
    """B-05 index: a bare str or non-str kind is rejected, not interpreted incompatibly."""
    e = Engine(SQLiteStore(tmp_path / "k.db"), clock=ManualClock())
    s = e.add_source(CTX, uri="mem://s", trust=0.9)
    e.assert_fact(CTX, subject="X", predicate="p", object="findme", source=s.id)
    with pytest.raises(ValidationError):
        e.search(CTX, text="findme", kinds="fact")  # bare str, not a tuple
    with pytest.raises(ValidationError):
        e.search(CTX, text="findme", kinds=(123,))  # non-str element
    assert e.search(CTX, text="findme", kinds=("fact",))  # correct usage still works
    e.close()


def test_rest_forwards_derived_from_and_memory_class(tmp_path) -> None:
    """B-04 boundaries: the REST/SDK assert must not silently drop provenance links."""
    import json
    import threading
    import urllib.request

    from epistemos.api.rest import make_server

    e = Engine(SQLiteStore(tmp_path / "f.db"), clock=ManualClock())
    src = e.add_source(CTX, uri="mem://s", trust=0.9)
    base = e.assert_fact(CTX, subject="B", predicate="p", object="base", source=src.id)

    srv = make_server(e, tokens={"tok": CTX})
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        body = {"subject": "A", "predicate": "p", "object": "v", "source": src.id,
                "derived_from": [base.id], "memory_class": "procedural"}
        req = urllib.request.Request(f"http://127.0.0.1:{port}/facts",
                                     data=json.dumps(body).encode(), method="POST")
        req.add_header("Authorization", "Bearer tok")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            fid = json.loads(resp.read())["id"]
        stored = e.get(CTX, fid)
        assert base.id in stored.derived_from, "derived_from was dropped at the REST boundary"
        assert stored.memory_class == "procedural", "memory_class was dropped at the REST boundary"
    finally:
        srv.shutdown()
        srv.server_close()
