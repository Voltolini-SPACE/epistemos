"""Generic consumer client (mission §13).

One surface — ``.context(...)`` and ``.expand(...)`` returning ``EPCTX/1`` — over three transports
with identical semantics:

* :class:`LocalContextClient` — in-process Engine + bound Principal.
* :class:`RestContextClient` — the REST boundary (``POST /context`` / ``/context/expand``).
* :class:`McpContextClient` — the MCP tool ``epistemos_context`` / ``epistemos_context_expand``.

In all three, identity is the client's binding (local Principal, REST token, MCP server principal);
the *arguments never carry authority* (§17, §19). A consumer writes to :class:`GenericContextClient`
and does not care which transport it holds.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, cast

from ..identity import Principal
from .wire import build_epctx

__all__ = [
    "GenericContextClient",
    "LocalContextClient",
    "RestContextClient",
    "McpContextClient",
]


class GenericContextClient(Protocol):
    """The consumption contract. Any transport that satisfies this is interchangeable."""

    def context(self, query: str | None, *, intent: str | None = ...,
                as_of: str | None = ..., requested_budget: int | None = ...,
                consumer_profile: dict[str, Any] | None = ...) -> dict[str, Any]: ...

    def expand(self, handle: str) -> dict[str, Any]: ...


class LocalContextClient:
    """Direct, in-process. The bound Principal scopes every call."""

    def __init__(self, engine: Any, principal: Principal) -> None:
        self._engine = engine
        self._p = principal

    def context(self, query: str | None, *, intent: str | None = None,
                as_of: str | None = None, requested_budget: int | None = None,
                consumer_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        return build_epctx(self._engine, self._p, query=query, intent=intent, as_of=as_of,
                           requested_budget=requested_budget, consumer_profile=consumer_profile)

    def expand(self, handle: str) -> dict[str, Any]:
        from .handles import expand as _expand
        return _expand(self._engine, self._p, handle)


class RestContextClient:
    """Talks to the REST boundary. Reuses :class:`~epistemos.sdk.RemoteClient` transport semantics
    (bearer token = identity; error bodies map to :mod:`epistemos.errors`)."""

    def __init__(self, base_url: str, token: str, *, namespace: str | None = None,
                 timeout: float = 10.0) -> None:
        from ..sdk import RemoteClient
        self._remote = RemoteClient(base_url, token, namespace=namespace, timeout=timeout)

    def context(self, query: str | None, *, intent: str | None = None,
                as_of: str | None = None, requested_budget: int | None = None,
                consumer_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query}
        if intent is not None:
            body["intent"] = intent
        if as_of is not None:
            body["as_of"] = as_of
        if requested_budget is not None:
            body["requested_budget"] = requested_budget
        if consumer_profile is not None:
            body["consumer_profile"] = consumer_profile
        return cast("dict[str, Any]", self._remote._request("POST", "/context", body=body))

    def expand(self, handle: str) -> dict[str, Any]:
        return cast("dict[str, Any]",
                    self._remote._request("POST", "/context/expand", body={"handle": handle}))


class McpContextClient:
    """Drives an :class:`~epistemos.mcp.MCPServer` through the ``tools/call`` JSON-RPC path, so it
    exercises the exact MCP boundary a real client would. Identity is the server's principal."""

    def __init__(self, mcp_server: Any) -> None:
        self._srv = mcp_server
        self._id = 0

    def _call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._id += 1
        resp = self._srv.handle({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                                 "params": {"name": tool, "arguments": arguments}})
        result = (resp or {}).get("result", {})
        text = result.get("content", [{}])[0].get("text", "{}")
        if result.get("isError"):
            raise RuntimeError(text)
        return cast("dict[str, Any]", json.loads(text))

    def context(self, query: str | None, *, intent: str | None = None,
                as_of: str | None = None, requested_budget: int | None = None,
                consumer_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"query": query}
        if intent is not None:
            args["intent"] = intent
        if as_of is not None:
            args["as_of"] = as_of
        if requested_budget is not None:
            args["requested_budget"] = requested_budget
        if consumer_profile is not None:
            args["consumer_profile"] = consumer_profile
        return self._call("epistemos_context", args)

    def expand(self, handle: str) -> dict[str, Any]:
        return self._call("epistemos_context_expand", {"handle": handle})
