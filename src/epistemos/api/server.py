"""Panel HTTP + SSE server (ADR-030/031/032).

A thin stdlib server that serves the vanilla panel assets, the **authorized** JSON read-model
(:class:`~epistemos.api.panel.PanelService`), and an **authorization-filtered** SSE event stream
(:mod:`epistemos.api.stream`). It adds no third-party dependency and binds ``127.0.0.1`` by default.

Security posture:

* identity comes only from the caller's bearer token (``Authorization`` header) or the
  ``eps_session`` cookie set by ``POST /api/session`` — never from a query/body. The token
  resolves to a ``Principal`` server-side; the browser cannot choose tenant/capability/visibility;
* a strict **Content-Security-Policy** (``default-src 'self'``; no external origins, no inline-less
  exceptions beyond the panel's own bundle) enforces **zero-egress at the browser**: the page cannot
  fetch a font, script, image, or beacon from any other host;
* the panel is **read-only** — there is no mutating route, so the UI grants no authority;
* every JSON payload and every streamed event has already passed ``Engine.is_readable`` in the
  read-model / stream layer. This server only transports authorized bytes.
"""

from __future__ import annotations

import json
import mimetypes
import os
from collections.abc import Callable, Mapping
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import BaseRequestHandler
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from ..core import Engine
from ..errors import (
    AuthorizationError,
    ConflictError,
    EpistemosError,
    IdentityError,
    NotFoundError,
    SchemaError,
    ValidationError,
)
from ..identity import Principal
from .panel import PanelService
from .rest import AuthResolver, StaticTokenAuth
from .stream import authorized_events

__all__ = ["PanelHTTPServer", "make_panel_server"]

_WEB_DIR = Path(__file__).resolve().parent.parent / "panel" / "web"
_SESSION_COOKIE = "eps_session"
_STREAM_POLL_SECONDS = 1.0
_STREAM_HEARTBEAT_SECONDS = 15.0

# a strict, self-only CSP — the panel is fully self-contained, so nothing external is permitted.
_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
    "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)

_STATUS_FOR = [
    (IdentityError, 401), (AuthorizationError, 403), (NotFoundError, 404),
    (ConflictError, 409), (SchemaError, 422), (ValidationError, 400),
]


def _status_for(exc: Exception) -> int:
    for typ, code in _STATUS_FOR:
        if isinstance(exc, typ):
            return code
    return 500


class PanelHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, addr: tuple[str, int], handler: type[BaseRequestHandler], *,
        engine: Engine, auth: AuthResolver, demo_identities: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(addr, handler)
        self.engine = engine
        self.panel = PanelService(engine)
        self.auth = auth
        self.demo_identities = demo_identities or []


def make_panel_server(
    engine: Engine, *, host: str = "127.0.0.1", port: int = 0,
    auth: AuthResolver | None = None, tokens: Mapping[str, Principal] | None = None,
    demo_identities: list[dict[str, str]] | None = None,
) -> PanelHTTPServer:
    """Create (not start) the panel server. Call ``serve_forever`` to run it."""
    if auth is None:
        if tokens is None:
            raise ValidationError("panel server requires an AuthResolver or a token map")
        auth = StaticTokenAuth(tokens)
    return PanelHTTPServer((host, port), _PanelHandler, engine=engine, auth=auth,
                           demo_identities=demo_identities)


class _PanelHandler(BaseHTTPRequestHandler):
    server_version = "epistemos-panel/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: Any) -> None:  # silence stderr noise
        return

    # -- helpers ------------------------------------------------------------
    def _srv(self) -> PanelHTTPServer:
        return cast(PanelHTTPServer, self.server)

    def _token(self) -> str | None:
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        raw = self.headers.get("Cookie")
        if raw:
            ck = SimpleCookie()
            try:
                ck.load(raw)
            except Exception:  # noqa: BLE001 - malformed cookie => unauthenticated
                return None
            if _SESSION_COOKIE in ck:
                return ck[_SESSION_COOKIE].value
        return None

    def _principal(self) -> Principal:
        token = self._token()
        if not token:
            raise IdentityError("no session — authenticate via POST /api/session")
        principal = self._srv().auth({"authorization": f"Bearer {token}"})
        if not isinstance(principal, Principal):
            raise IdentityError("authentication did not resolve a valid Principal")
        return principal

    def _security_headers(self) -> None:
        self.send_header("Content-Security-Policy", _CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")

    def _send_json(self, code: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _fail(self, exc: Exception) -> None:
        code = _status_for(exc)
        kind = type(exc).__name__ if isinstance(exc, EpistemosError) else "InternalError"
        # error bodies never distinguish forbidden-vs-absent for a specific id (no oracle)
        msg = str(exc) if code not in (401, 403, 404) else _SAFE_ERROR.get(code, "error")
        self._send_json(code, {"error": kind if code < 500 else "InternalError", "message": msg})

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 1_000_000:
            raise ValidationError("request body too large")
        try:
            data = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid JSON body: {exc}") from exc
        if not isinstance(data, dict):
            raise ValidationError("body must be a JSON object")
        return data

    # -- routing ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/stream":
                self._stream()
                return
            if path.startswith("/api/"):
                q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                self._send_json(200, self._api_get(path, q))
                return
            self._serve_static(path)
        except Exception as exc:  # noqa: BLE001 - boundary maps all errors
            self._fail(exc)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/session":
                self._session()
                return
            if path == "/api/search":
                principal = self._principal()
                body = self._body()
                self._send_json(200, self._srv().panel.search(
                    principal, text=body.get("text"), subject=body.get("subject"),
                    predicate=body.get("predicate"), object=body.get("object"),
                    kinds=tuple(body["kinds"]) if body.get("kinds") else None,
                    limit=int(body.get("limit", 20)),
                    believed_only=bool(body.get("believed_only", False))))
                return
            self._send_json(404, {"error": "NotFound", "message": "no such route"})
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)

    def _session(self) -> None:
        """Exchange a valid token for an HttpOnly, SameSite=Strict session cookie (keeps the token
        out of URLs and JS-readable storage). Fails closed on an unknown token."""
        body = self._body()
        token = str(body.get("token", ""))
        principal = self._srv().auth({"authorization": f"Bearer {token}"})  # validates or raises
        if not isinstance(principal, Principal):
            raise IdentityError("invalid token")
        payload = json.dumps({"ok": True, "agent": principal.agent}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header(
            "Set-Cookie",
            f"{_SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400",
        )
        self._security_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _api_get(self, path: str, q: dict[str, str]) -> Any:
        srv = self._srv()
        if path == "/api/demo/identities":
            return {"identities": srv.demo_identities}  # empty unless launched with --demo
        principal = self._principal()
        p = srv.panel
        if path == "/api/whoami":
            return {"tenant": principal.tenant, "agent": principal.agent,
                    "namespace": principal.namespace,
                    "capabilities": sorted(principal.capabilities)}
        if path == "/api/overview":
            return p.overview(principal)
        if path == "/api/counts":
            return p.counts(principal)
        if path == "/api/graph":
            return p.knowledge_graph(
                principal, focus=q.get("focus") or None, hops=int(q.get("hops", 1)),
                kinds=q["kinds"].split(",") if q.get("kinds") else None,
                limit=int(q.get("limit", 1500)))
        if path == "/api/graph/expand":
            return p.expand(principal, q["node"])
        if path == "/api/list":
            return p.list_objects(principal, kind=q.get("kind", "claim"),
                                  limit=int(q.get("limit", 50)), offset=int(q.get("offset", 0)))
        if path == "/api/claim":
            return p.claim_detail(principal, q["id"])
        if path == "/api/belief":
            return p.belief(principal, q["id"])
        if path == "/api/evidence":
            return p.evidence_detail(principal, q["id"])
        if path == "/api/explain":
            return p.explain(principal, q["id"])
        if path == "/api/activity":
            return p.activity(principal, since_seq=int(q.get("since", 0)),
                              limit=int(q.get("limit", 200)))
        if path == "/api/asof":
            return p.as_of(principal, at_tx=q["at"],
                           kinds=q["kinds"].split(",") if q.get("kinds") else None)
        if path == "/api/spaces":
            return p.spaces(principal)
        if path == "/api/agents":
            return p.agents(principal)
        if path == "/api/sources":
            return p.sources(principal)
        if path == "/api/health":
            return p.health(principal)
        if path == "/api/search":
            return p.search(principal, text=q.get("text"), limit=int(q.get("limit", 20)))
        raise NotFoundError("no such route")

    # -- SSE stream ---------------------------------------------------------
    def _stream(self) -> None:
        """Authorized SSE tail of the ledger. Resumes from ``Last-Event-ID`` and heartbeats when
        idle. Every event has already passed the read-model firewall (ADR-032)."""
        import time

        principal = self._principal()
        engine = self._srv().engine
        try:
            since = int(self.headers.get("Last-Event-ID") or 0)
        except ValueError:
            since = 0
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self._security_headers()
        self.end_headers()
        self.close_connection = False
        last_beat = time.monotonic()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                events = authorized_events(engine, principal, since_seq=since)
                for ev in events:
                    since = max(since, ev["seq"])
                    chunk = (f"id: {ev['seq']}\n"
                             f"event: {ev['kind']}\n"
                             f"data: {json.dumps(ev)}\n\n").encode()
                    self.wfile.write(chunk)
                if events:
                    self.wfile.flush()
                    last_beat = time.monotonic()
                elif time.monotonic() - last_beat >= _STREAM_HEARTBEAT_SECONDS:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    last_beat = time.monotonic()
                time.sleep(_STREAM_POLL_SECONDS)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True  # client went away — end the thread quietly

    # -- static -------------------------------------------------------------
    def _serve_static(self, path: str) -> None:
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (_WEB_DIR / rel).resolve()
        web_root = _WEB_DIR.resolve()
        # path-traversal defense: the resolved target must stay under the web root
        inside = os.path.commonpath([str(target), str(web_root)]) == str(web_root)
        if not inside or not target.is_file():
            # SPA fallback: unknown non-file, non-api path serves the shell (client-side routing)
            if not path.startswith("/api/") and "." not in Path(path).name:
                target = web_root / "index.html"
            else:
                self._send_json(404, {"error": "NotFound", "message": "not found"})
                return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)


_SAFE_ERROR = {401: "authentication required", 403: "not authorized", 404: "not found"}


_RouteHandler = Callable[..., Any]
