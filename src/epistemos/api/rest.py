"""REST boundary (mission §20, checkpoint V).

A **thin** HTTP adapter over :class:`~epistemos.core.Engine` built on the standard-library
``http.server`` (no third-party dependency). It contains no domain logic: every request is
authenticated to a :class:`~epistemos.identity.Principal` and forwarded to the Engine, and
Engine exceptions are mapped to HTTP status codes.

Security posture (mission §20):

* binds ``127.0.0.1`` by default — never ``0.0.0.0`` implicitly;
* authentication is **pluggable** (``AuthResolver``); the default is a static bearer-token
  map. No token -> 401. The client cannot choose its own tenant — identity comes from the
  token, so a request body can never escalate scope;
* no interface has implicit authority.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import BaseRequestHandler
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from ..core import Engine
from ..errors import (
    AuthorizationError,
    ConflictError,
    EpistemosError,
    IdentityError,
    IntegrityError,
    NotFoundError,
    SchemaError,
    ValidationError,
)
from ..identity import Principal

__all__ = ["AuthResolver", "StaticTokenAuth", "make_server", "EpistemosHTTPServer"]

AuthResolver = Callable[[Mapping[str, str]], Principal]

_MAX_BODY = 8 * 1024 * 1024

_STATUS_FOR = [
    (IdentityError, 401),
    (AuthorizationError, 403),  # includes TenantIsolationError
    (NotFoundError, 404),
    (ConflictError, 409),
    (SchemaError, 422),
    (ValidationError, 400),
    (IntegrityError, 500),
]


class StaticTokenAuth:
    """Default pluggable auth: bearer token -> fixed Principal. Fail closed on unknown."""

    def __init__(self, tokens: Mapping[str, Principal]) -> None:
        self._tokens = dict(tokens)

    def __call__(self, headers: Mapping[str, str]) -> Principal:
        auth = headers.get("authorization") or headers.get("Authorization") or ""
        m = re.match(r"Bearer\s+(\S+)$", auth)
        if not m:
            raise IdentityError("missing or malformed Authorization header")
        principal = self._tokens.get(m.group(1))
        if principal is None:
            raise IdentityError("unknown token")
        ns = headers.get("x-eps-namespace")
        if ns:  # namespace switch is allowed within the token's tenant/agent
            principal = principal.with_namespace(ns)
        return principal


def _status_for(exc: Exception) -> int:
    for typ, code in _STATUS_FOR:
        if isinstance(exc, typ):
            return code
    return 500


class EpistemosHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        addr: tuple[str, int],
        handler: type[BaseRequestHandler],
        *,
        engine: Engine,
        auth: AuthResolver,
    ) -> None:
        super().__init__(addr, handler)
        self.engine = engine
        self.auth = auth


def make_server(
    engine: Engine,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    auth: AuthResolver | None = None,
    tokens: Mapping[str, Principal] | None = None,
) -> EpistemosHTTPServer:
    """Create (not start) a localhost HTTP server. Call ``serve_forever`` to run it."""
    if auth is None:
        if tokens is None:
            raise ValidationError("REST server requires either an AuthResolver or a token map")
        auth = StaticTokenAuth(tokens)
    return EpistemosHTTPServer((host, port), _Handler, engine=engine, auth=auth)


class _Handler(BaseHTTPRequestHandler):
    server_version = "epistemos-rest/0.1"
    protocol_version = "HTTP/1.1"

    # -- plumbing ------------------------------------------------------------
    def log_message(self, *args: Any) -> None:  # silence default stderr logging
        return

    def _engine(self) -> Engine:
        return cast(Engine, self.server.engine)  # type: ignore[attr-defined]

    def _principal(self) -> Principal:
        headers = {k.lower(): v for k, v in self.headers.items()}
        principal = self.server.auth(headers)  # type: ignore[attr-defined]
        # Fail closed if a pluggable AuthResolver returns a non-Principal (e.g. None instead of
        # raising). Otherwise a resolver bug would reach the Engine as principal=None and, for
        # /export, trigger the unscoped whole-store dump (EPISTEMOS-03, B-01).
        if not isinstance(principal, Principal):
            raise IdentityError("authentication did not resolve a valid Principal")
        return principal

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > _MAX_BODY:
            raise ValidationError("request body too large")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid JSON body: {exc}") from exc
        if not isinstance(data, dict):
            raise ValidationError("request body must be a JSON object")
        return data

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _fail(self, exc: Exception) -> None:
        code = _status_for(exc)
        kind = type(exc).__name__ if isinstance(exc, EpistemosError) else "InternalError"
        self._send(code, {"error": kind, "message": str(exc)})

    # -- routing -------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self._route("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._route("POST")

    def _drain_body(self) -> None:
        """Consume any unread request body so a keep-alive connection stays framed.

        Without this, an error before ``_body()`` leaves the POST payload in the socket and the
        next request on the same connection is parsed starting mid-body — HTTP request smuggling
        on a pipelined connection (EPISTEMOS-03, B-05)."""
        try:
            remaining = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.close_connection = True
            return
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)

    def _route(self, method: str) -> None:
        body_consumed = False
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            principal = self._principal()
            engine = self._engine()
            handler = _ROUTES.get((method, path))
            if handler is None:
                m = re.match(r"^/explain/([^/]+)$", parsed.path)
                if method == "GET" and m:
                    self._send(200, engine.explain(principal, m.group(1)))
                    return
                self._send(404, {"error": "NotFound", "message": "no such route"})
                return
            if method == "POST":
                body = self._body()
                body_consumed = True
            else:
                body = {}
            result = handler(engine, principal, query, body)
            self._send(200 if method == "GET" else 201 if path == "/facts" else 200, result)
        except Exception as exc:  # noqa: BLE001 - boundary maps all errors to HTTP
            if method == "POST" and not body_consumed:
                self._drain_body()
            self._fail(exc)


# -- route handlers (thin: validate-free, straight to the engine) -----------
def _health(
    engine: Engine, principal: Principal, q: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    return engine.health(principal, verify=q.get("verify") == "1")


def _add_source(
    engine: Engine, principal: Principal, q: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    s = engine.add_source(
        principal, uri=body["uri"], source_kind=body.get("source_kind", "unknown"),
        trust=float(body.get("trust", 0.5)), metadata=body.get("metadata"),
    )
    return {"id": s.id}


def _assert_fact(
    engine: Engine, principal: Principal, q: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    if body.get("derived_from") is not None:  # do not silently drop provenance links (B-04)
        extra["derived_from"] = body["derived_from"]
    if body.get("memory_class") is not None:
        extra["memory_class"] = body["memory_class"]
    f = engine.assert_fact(
        principal, subject=body["subject"], predicate=body["predicate"],
        object=body.get("object"), valid_from=body.get("valid_from"),
        valid_to=body.get("valid_to"), source=body.get("source"),
        confidence=float(body.get("confidence", 1.0)), metadata=body.get("metadata"),
        **extra,
    )
    return {"id": f.id, "fact": f.to_dict()}


def _current(
    engine: Engine, principal: Principal, q: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    return {"value": engine.current(principal, subject=q["subject"], predicate=q["predicate"])}


def _search(
    engine: Engine, principal: Principal, q: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    return {"results": engine.search(
        principal, text=body.get("text"), subject=body.get("subject"),
        predicate=body.get("predicate"), object=body.get("object"),
        limit=int(body.get("limit", 10)), believed_only=bool(body.get("believed_only", False)),
    )}


def _timeline(
    engine: Engine, principal: Principal, q: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    tl = engine.timeline(principal, subject=q["subject"], predicate=q.get("predicate"))
    return {"timeline": tl}


def _export(
    engine: Engine, principal: Principal, q: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    # Always scope-limited: the caller's token decides what it may read. A whole-store export
    # (scope='all') additionally requires the 'admin' capability, enforced by the Engine.
    return engine.export(principal, scope="all" if q.get("scope") == "all" else "principal")


_RouteHandler = Callable[[Engine, Principal, dict[str, str], dict[str, Any]], dict[str, Any]]

_ROUTES: dict[tuple[str, str], _RouteHandler] = {
    ("GET", "/health"): _health,
    ("POST", "/sources"): _add_source,
    ("POST", "/facts"): _assert_fact,
    ("GET", "/facts/current"): _current,
    ("POST", "/search"): _search,
    ("GET", "/timeline"): _timeline,
    ("GET", "/export"): _export,
}
