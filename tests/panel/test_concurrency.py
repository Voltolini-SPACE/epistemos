"""Concurrency / race regression (EPISTEMOS-PANEL-HARDENING-01 §8).

A writer thread ingests into the same Engine that concurrent HTTP readers hammer. Pins that under
``ThreadingHTTPServer`` the panel never returns a 500, never serves a torn count, and never leaks a
private object mid-write. The exhaustive 30x battery lives in the mission log; this is the fast,
deterministic guard.
"""
from __future__ import annotations

import http.client
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from tests.panel.conftest import SECRET, principal

from epistemos import Engine
from epistemos.api.server import make_panel_server
from epistemos.storage import MemoryStore


@pytest.fixture
def racing_server():
    eng = Engine(MemoryStore())
    alice = principal("alice", extra=frozenset({"knowledge.share", "claim.confirm"}))
    bob = principal("bob")
    team = eng.create_space(alice, name="team", visibility="TEAM")
    eng.grant_capability(alice, space_id=team.id, agent="bob")
    eng.create_claim(alice, subject="Shared", predicate="is", object="ok", space=team.id)
    eng.create_claim(alice, subject="Secret", predicate="is", object=SECRET)  # private to alice
    srv = make_panel_server(eng, host="127.0.0.1", port=0, tokens={"A": alice, "B": bob})
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    yield eng, alice, team, host, port
    srv.shutdown()
    srv.server_close()
    eng.close()


def _get(host, port, path, token):
    c = http.client.HTTPConnection(host, port, timeout=10)
    c.request("GET", path, headers={"Authorization": f"Bearer {token}"})
    r = c.getresponse()
    b = r.read()
    st = r.status
    c.close()
    return st, b


def test_reads_are_consistent_and_leakfree_under_concurrent_writes(racing_server):
    eng, alice, team, host, port = racing_server
    errors: list[str] = []
    lock = threading.Lock()
    stop = threading.Event()

    def note(msg: str) -> None:
        with lock:
            errors.append(msg)

    def writer() -> None:
        i = 0
        while not stop.is_set() and i < 40:
            i += 1
            try:
                c = eng.create_claim(alice, subject=f"C{i}", predicate="is", object=f"v{i}",
                                     space=team.id)
                ev = eng.create_evidence(alice, title=f"e{i}", uri=f"https://x/{i}", space=team.id)
                eng.attach_evidence(alice, evidence_id=ev.id, to_claim=c.id, relation="supports")
                if i % 2 == 0:
                    eng.review_claim(alice, c.id, verdict="confirm")
                eng.create_claim(alice, subject=f"S{i}", predicate="is", object=SECRET)  # private
            except Exception as e:  # noqa: BLE001
                note(f"writer {type(e).__name__}: {e}")

    def reader(_n: int) -> None:
        for p in ("/api/overview", "/api/counts", "/api/graph", "/api/list?kind=claim",
                  "/api/activity", "/api/search?text=C", "/api/health"):
            st, b = _get(host, port, p, "A")
            if st == 500:
                note(f"A {p} -> 500")
            if p == "/api/counts" and st == 200:
                j = json.loads(b)
                s = sum(j[k] for k in ("entities", "facts", "claims", "evidence",
                                       "reviews", "sources", "decisions"))
                if s != j["knowledge_objects"]:
                    note(f"torn counts {s} != {j['knowledge_objects']}")
        for p in ("/api/counts", "/api/graph", f"/api/search?text={SECRET}",
                  "/api/list?kind=claim"):
            st, b = _get(host, port, p, "B")
            if st == 500:
                note(f"B {p} -> 500")
            if SECRET.encode() in b:
                note(f"PRIVATE LEAK to bob at {p}")

    wt = threading.Thread(target=writer)
    wt.start()
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(reader, range(30)))
    stop.set()
    wt.join(timeout=5)

    assert not errors, "concurrency defects:\n" + "\n".join(errors[:15])
