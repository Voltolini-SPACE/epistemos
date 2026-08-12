"""SSE / realtime regressions (EPISTEMOS-PANEL-HARDENING-01 §7).

Pins the measured guarantees of the authorized event stream: every authorized event is delivered
exactly once, in ledger order, and a reconnect with ``Last-Event-ID`` resumes with no loss and no
re-delivery of already-seen events. A malformed ``Last-Event-ID`` must not crash the stream.
"""
from __future__ import annotations

import contextlib
import socket
import threading
import time

import pytest
from tests.panel.conftest import principal

from epistemos import Engine
from epistemos.api.server import make_panel_server
from epistemos.storage import MemoryStore


@pytest.fixture
def sse_env():
    eng = Engine(MemoryStore())
    a = principal("alice")
    srv = make_panel_server(eng, host="127.0.0.1", port=0, tokens={"A": a})
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    yield eng, a, host, port
    srv.shutdown()
    srv.server_close()
    eng.close()


class _SSEClient:
    def __init__(self, host, port, last_event_id=None):
        self.sock = socket.create_connection((host, port), timeout=8)
        req = ("GET /api/stream HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer A\r\n"
               "Accept: text/event-stream\r\n")
        if last_event_id is not None:
            req += f"Last-Event-ID: {last_event_id}\r\n"
        req += "\r\n"
        self.sock.sendall(req.encode())
        self.buf = b""
        self.ids: list[int] = []
        self.status = None

    def pump(self, seconds):
        end = time.time() + seconds
        self.sock.settimeout(0.5)
        while time.time() < end:
            try:
                chunk = self.sock.recv(65536)
            except TimeoutError:
                continue
            except OSError:
                break
            if not chunk:
                break
            self.buf += chunk
            if self.status is None and b"\r\n\r\n" in self.buf:
                head, self.buf = self.buf.split(b"\r\n\r\n", 1)
                self.status = int(head.split(b" ")[1])
            for line in self.buf.split(b"\n"):
                if line.startswith(b"id:"):
                    with contextlib.suppress(ValueError):
                        self.ids.append(int(line[3:].strip()))
            if b"\n\n" in self.buf:
                self.buf = self.buf.rsplit(b"\n\n", 1)[1]

    def close(self):
        with contextlib.suppress(OSError):
            self.sock.close()


def test_stream_delivers_each_event_once_in_order(sse_env):
    eng, a, host, port = sse_env
    eng.create_claim(a, subject="seed", predicate="is", object="0")
    client = _SSEClient(host, port)
    time.sleep(0.3)
    for i in range(15):
        eng.create_claim(a, subject=f"c{i}", predicate="is", object=str(i))
        time.sleep(0.01)
    client.pump(2.5)
    client.close()
    seen = client.ids
    head = eng.store.event_count()
    assert client.status == 200
    assert len(seen) == len(set(seen)), f"duplicates: {seen}"                 # DUPLICATE_RATE = 0
    assert seen == sorted(seen), f"out of order: {seen}"                       # ordering
    assert set(range(1, head + 1)) - set(seen) == set(), "event loss"          # EVENT_LOSS = 0


def test_reconnect_resumes_without_loss_or_redelivery(sse_env):
    eng, a, host, port = sse_env
    c1 = _SSEClient(host, port)
    time.sleep(0.3)
    for i in range(8):
        eng.create_claim(a, subject=f"a{i}", predicate="is", object=str(i))
        time.sleep(0.01)
    c1.pump(2.0)
    last = max(c1.ids)
    c1.close()

    c2 = _SSEClient(host, port, last_event_id=last)
    time.sleep(0.3)
    for i in range(8):
        eng.create_claim(a, subject=f"b{i}", predicate="is", object=str(i))
        time.sleep(0.01)
    c2.pump(2.0)
    c2.close()
    head = eng.store.event_count()
    assert all(s > last for s in c2.ids), "re-delivered already-seen events"   # no re-delivery
    assert set(range(last + 1, head + 1)) - set(c2.ids) == set(), "resume loss"  # no loss


def test_malformed_last_event_id_does_not_crash(sse_env):
    eng, a, host, port = sse_env
    eng.create_claim(a, subject="x", predicate="is", object="0")
    c = _SSEClient(host, port, last_event_id="not-a-number")
    c.pump(1.5)
    c.close()
    assert c.status == 200  # falls back to seq 0, streams, no crash
    assert c.ids  # still received events
