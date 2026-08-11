"""Python SDK (mission §20, checkpoint X).

Two backends, one surface, the same error semantics:

* :class:`LocalClient` wraps an in-process :class:`~epistemos.core.Engine` (a bound
  Principal); it *is* the domain — no duplicated rules.
* :class:`RemoteClient` speaks to the REST boundary over ``http.client`` (stdlib) and maps
  HTTP error responses back to the same :mod:`epistemos.errors` exception types, so callers
  handle failures identically whether local or remote.
"""

from __future__ import annotations

import json
from typing import Any, cast
from urllib.parse import urlencode, urlparse

from . import errors as _errors
from .core import Engine
from .identity import Principal

__all__ = ["LocalClient", "RemoteClient"]

_ERROR_TYPES = {
    "ValidationError": _errors.ValidationError,
    "SchemaError": _errors.SchemaError,
    "IdentityError": _errors.IdentityError,
    "AuthorizationError": _errors.AuthorizationError,
    "TenantIsolationError": _errors.TenantIsolationError,
    "NotFoundError": _errors.NotFoundError,
    "ConflictError": _errors.ConflictError,
    "IntegrityError": _errors.IntegrityError,
}


class LocalClient:
    """Direct, in-process client. The bound Principal scopes every call."""

    def __init__(self, engine: Engine, principal: Principal) -> None:
        self._engine = engine
        self._p = principal

    def add_source(self, *, uri: str, trust: float = 0.5, source_kind: str = "unknown") -> str:
        return self._engine.add_source(self._p, uri=uri, trust=trust,
                                       source_kind=source_kind).id

    def assert_fact(self, *, subject: str, predicate: str, object: str | None = None,
                    **kw: Any) -> str:
        return self._engine.assert_fact(self._p, subject=subject, predicate=predicate,
                                        object=object, **kw).id

    def current(self, *, subject: str, predicate: str) -> str | None:
        return self._engine.current(self._p, subject=subject, predicate=predicate)

    def search(self, **kw: Any) -> list[dict[str, Any]]:
        return self._engine.search(self._p, **kw)

    def timeline(self, *, subject: str, predicate: str | None = None) -> list[dict[str, Any]]:
        return self._engine.timeline(self._p, subject=subject, predicate=predicate)

    def explain(self, obj_id: str) -> dict[str, Any]:
        return self._engine.explain(self._p, obj_id)

    def health(self) -> dict[str, Any]:
        return self._engine.health(self._p)

    def export(self) -> dict[str, Any]:
        return self._engine.export()


class RemoteClient:
    """REST client. Same method names & error types as :class:`LocalClient`."""

    def __init__(self, base_url: str, token: str, *, namespace: str | None = None,
                 timeout: float = 10.0) -> None:
        url = urlparse(base_url)
        if not url.hostname:
            raise _errors.ValidationError(f"invalid base_url: {base_url!r}")
        self._scheme = url.scheme or "http"
        self._host: str = url.hostname
        self._port: int | None = url.port
        self._token = token
        self._namespace = namespace
        self._timeout = timeout

    # -- transport -----------------------------------------------------------
    def _request(self, method: str, path: str, *, query: dict[str, Any] | None = None,
                 body: dict[str, Any] | None = None) -> Any:
        import http.client

        conn_cls = http.client.HTTPSConnection if self._scheme == "https" \
            else http.client.HTTPConnection
        conn = conn_cls(self._host, self._port, timeout=self._timeout)
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        if self._namespace:
            headers["X-Eps-Namespace"] = self._namespace
        full = path + ("?" + urlencode(query) if query else "")
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        try:
            conn.request(method, full, body=payload, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            data = json.loads(raw) if raw else {}
        finally:
            conn.close()
        if resp.status >= 400:
            self._raise(data)
        return data

    @staticmethod
    def _raise(data: dict[str, Any]) -> None:
        kind = data.get("error", "EpistemosError")
        message = data.get("message", "remote error")
        exc_type = _ERROR_TYPES.get(kind, _errors.EpistemosError)
        raise exc_type(message)

    # -- API (mirrors LocalClient) ------------------------------------------
    def add_source(self, *, uri: str, trust: float = 0.5, source_kind: str = "unknown") -> str:
        body = {"uri": uri, "trust": trust, "source_kind": source_kind}
        return cast(str, self._request("POST", "/sources", body=body)["id"])

    def assert_fact(self, *, subject: str, predicate: str, object: str | None = None,
                    **kw: Any) -> str:
        body = {"subject": subject, "predicate": predicate, "object": object, **kw}
        return cast(str, self._request("POST", "/facts", body=body)["id"])

    def current(self, *, subject: str, predicate: str) -> str | None:
        data = self._request("GET", "/facts/current",
                             query={"subject": subject, "predicate": predicate})
        return cast("str | None", data["value"])

    def search(self, **kw: Any) -> list[dict[str, Any]]:
        return cast("list[dict[str, Any]]", self._request("POST", "/search", body=kw)["results"])

    def timeline(self, *, subject: str, predicate: str | None = None) -> list[dict[str, Any]]:
        q = {"subject": subject}
        if predicate:
            q["predicate"] = predicate
        return cast("list[dict[str, Any]]",
                    self._request("GET", "/timeline", query=q)["timeline"])

    def explain(self, obj_id: str) -> dict[str, Any]:
        return cast("dict[str, Any]", self._request("GET", f"/explain/{obj_id}"))

    def health(self) -> dict[str, Any]:
        return cast("dict[str, Any]", self._request("GET", "/health"))

    def export(self) -> dict[str, Any]:
        return cast("dict[str, Any]", self._request("GET", "/export"))
