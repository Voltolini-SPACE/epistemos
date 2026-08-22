"""``python -m epistemos.panel`` — launch the panel server.

Modes:

* ``--demo`` (default when no store is given): build a REAL demo corpus (real objects via the real
  Engine API — not mocks) in an in-memory store and expose demo identities for the login picker.
* ``--db PATH``: serve a real, persisted SQLite-backed Engine. Tokens then come from
  ``EPISTEMOS_PANEL_TOKENS`` (``token=agent`` pairs) — no identities are exposed for a real store.
* ``--live-demo``: additionally run a slow generator that appends REAL objects through the Engine
  API so the realtime stream shows genuine ledger activity (not a fake timer, §36).

Binds ``127.0.0.1``; nothing leaves the machine (local-first, zero-egress).
"""

from __future__ import annotations

import argparse
import errno
import os
import sys
import threading
import time

from ..api.server import make_panel_server
from ..core import Engine
from ..identity import Principal
from ..storage import MemoryStore, SQLiteStore
from .demo import make_identities, seed


def _live_demo(engine: Engine, ids: object) -> None:  # pragma: no cover - background generator
    """Append REAL objects at a slow, human pace so the SSE stream shows genuine activity. Each
    object is created through the public Engine API and appended to the real ledger — no fake timer
    events. Labeled to the 'demo-feed' agent so the source of the real activity is transparent."""
    from ..identity import _DEFAULT_CAPS  # noqa: PLC0415
    from .demo import _NS, _TENANT  # noqa: PLC0415

    feed = Principal(tenant=_TENANT, agent="demo-feed", namespace=_NS, capabilities=_DEFAULT_CAPS)
    space_id = getattr(ids, "research", None)
    subjects = ["Company X", "Company Y", "Company Z", "Market", "Sector"]
    preds = ["signal", "guidance", "sentiment", "exposure", "trend"]
    objs = ["upgraded", "downgraded", "stable", "volatile", "expanding"]
    n = 0
    while True:
        time.sleep(13.0)
        try:
            s, p, o = subjects[n % 5], preds[(n // 5) % 5], objs[(n * 3) % 5]
            claim = engine.create_claim(feed, subject=s, predicate=p, object=f"{o} ({n})",
                                        space=space_id)
            ev = engine.create_evidence(feed, evidence_kind="observation",
                                        title=f"telemetry {s} #{n}", uri=f"sensor://{s}/{n}",
                                        space=space_id)
            engine.attach_evidence(feed, evidence_id=ev.id, to_claim=claim.id, relation="supports")
            n += 1
        except Exception:  # noqa: BLE001, S110 - a demo generator must never crash the server
            pass


def _tokens_from_env() -> dict[str, Principal]:
    raw = os.environ.get("EPISTEMOS_PANEL_TOKENS", "")
    tenant = os.environ.get("EPISTEMOS_PANEL_TENANT", "default")
    ns = os.environ.get("EPISTEMOS_PANEL_NAMESPACE", "kb")
    out: dict[str, Principal] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if "=" in pair:
            token, agent = pair.split("=", 1)
            out[token.strip()] = Principal(tenant=tenant, agent=agent.strip(), namespace=ns)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m epistemos.panel")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--db", default=None, help="serve a persisted SQLite Engine at this path")
    ap.add_argument("--demo", action="store_true", help="seed a real demo corpus (in-memory)")
    ap.add_argument("--live-demo", action="store_true",
                    help="also run a slow real-object generator for live-stream demos")
    args = ap.parse_args(argv)

    demo_mode = args.demo or (args.db is None)
    if args.db:
        engine = Engine(SQLiteStore(args.db))
        tokens = _tokens_from_env()
        demo_identities: list[dict[str, str]] = []
        if not tokens:
            print("error: --db requires EPISTEMOS_PANEL_TOKENS=token=agent[,token=agent]",
                  file=sys.stderr)
            return 2
    else:
        engine = Engine(MemoryStore())
        ids = make_identities()
        idmap = seed(engine, ids)
        tokens = ids.tokens
        demo_identities = ids.identities
        if args.live_demo:
            class _Ids:
                research = idmap["research_space"]
            threading.Thread(target=_live_demo, args=(engine, _Ids()), daemon=True).start()

    try:
        server = make_panel_server(engine, host=args.host, port=args.port, tokens=tokens,
                                   demo_identities=demo_identities)
    except OSError as exc:
        engine.close()
        if exc.errno == errno.EADDRINUSE:
            print(f"error: {args.host}:{args.port} is already in use.\n"
                  f"       Another process is listening there — stop it, or pick a free port:\n"
                  f"         epistemos panel --demo --port {args.port + 1}",
                  file=sys.stderr)
        elif exc.errno in (errno.EACCES, errno.EPERM):
            print(f"error: not allowed to bind {args.host}:{args.port}.\n"
                  f"       Ports below 1024 need elevated privileges — pick a higher port:\n"
                  f"         epistemos panel --demo --port 8787",
                  file=sys.stderr)
        elif exc.errno == errno.EADDRNOTAVAIL:
            print(f"error: {args.host} is not an address on this machine.\n"
                  f"       Use --host 127.0.0.1 to serve locally.",
                  file=sys.stderr)
        else:
            print(f"error: could not start the Panel on {args.host}:{args.port} — {exc}",
                  file=sys.stderr)
        return 2
    host, port = str(server.server_address[0]), int(server.server_address[1])
    url = f"http://{host}:{port}/"
    print(f"EPISTEMOS Panel — {url}  (local-first, zero-egress)")
    if demo_mode:
        print("DEMO MODE — real corpus, demo identities:")
        for ident in demo_identities:
            print(f"  {ident['token']:14} → {ident['agent']:8} ({ident['label']})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        server.server_close()
        engine.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
