"""MCP boundary (mission §20, checkpoint W). MCP is treated as a HOSTILE frontier.

Design rules enforced here:

* **No generic power tools.** There is no ``execute``, ``eval``, ``query_raw_sql``,
  ``query_raw_cypher``, ``filesystem_read`` or ``url_fetch``. Only a fixed registry of
  narrow, validated operations that map to Engine methods.
* **Identity is server-side.** The connected client's :class:`~epistemos.identity.Principal`
  is configured when the server starts; tool *arguments can never choose tenant/namespace*,
  so a malicious client cannot escalate scope.
* **All arguments are data.** They are validated by the Engine; injection/prompt payloads
  are stored inertly (see the security tests).

The transport-independent :meth:`MCPServer.handle` implements JSON-RPC 2.0 so the boundary
logic is unit-testable without a real stdio pipe. :meth:`MCPServer.serve_stdio` runs it.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

from ..core import Engine
from ..errors import EpistemosError
from ..identity import Principal

__all__ = ["MCPServer", "TOOLS"]

PROTOCOL_VERSION = "2024-11-05"


def _tool(engine: Engine, principal: Principal, name: str, args: dict[str, Any]) -> Any:
    if name == "assert_fact":
        f = engine.assert_fact(
            principal, subject=args["subject"], predicate=args["predicate"],
            object=args.get("object"), valid_from=args.get("valid_from"),
            valid_to=args.get("valid_to"), confidence=float(args.get("confidence", 1.0)),
            source=args.get("source"),
        )
        return {"id": f.id}
    if name == "current":
        return {"value": engine.current(principal, subject=args["subject"],
                                        predicate=args["predicate"])}
    if name == "search":
        return {"results": engine.search(
            principal, text=args.get("text"), subject=args.get("subject"),
            predicate=args.get("predicate"), limit=int(args.get("limit", 10)))}
    if name == "timeline":
        return {"timeline": engine.timeline(principal, subject=args["subject"],
                                            predicate=args.get("predicate"))}
    if name == "explain":
        return engine.explain(principal, args["id"])
    if name == "record_decision":
        d = engine.record_decision(principal, statement=args["statement"],
                                   evidence=args.get("evidence", []))
        return {"id": d.id}
    if name == "health":
        return engine.health(principal)
    if name == "epistemos_context":
        profile = args.get("consumer_profile")
        if profile is not None and not isinstance(profile, dict):
            raise ValueError("consumer_profile must be an object")
        budget = args.get("requested_budget")
        return engine.epctx(
            principal, args.get("query"), intent=args.get("intent"), as_of=args.get("as_of"),
            requested_budget=int(budget) if isinstance(budget, int) else None,
            consumer_profile=profile)
    if name == "epistemos_context_expand":
        handle = args.get("handle")
        if not isinstance(handle, str) or not handle:
            raise ValueError("handle must be a non-empty string")
        return engine.expand(principal, handle)
    raise KeyError(name)


# Fixed registry (name -> JSON Schema). NOTE the absence of any generic execute/query tool.
TOOLS: dict[str, dict[str, Any]] = {
    "assert_fact": {
        "description": "Assert a bitemporal (subject, predicate, object) fact.",
        "inputSchema": {
            "type": "object",
            "required": ["subject", "predicate"],
            "properties": {
                "subject": {"type": "string"}, "predicate": {"type": "string"},
                "object": {"type": ["string", "null"]},
                "valid_from": {"type": "string"}, "valid_to": {"type": "string"},
                "confidence": {"type": "number"}, "source": {"type": "string"},
            },
        },
    },
    "current": {
        "description": "Get the value currently believed for (subject, predicate).",
        "inputSchema": {"type": "object", "required": ["subject", "predicate"],
                        "properties": {"subject": {"type": "string"},
                                       "predicate": {"type": "string"}}},
    },
    "search": {
        "description": "Explainable retrieval over the caller's scope.",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"},
                        "subject": {"type": "string"}, "predicate": {"type": "string"},
                        "limit": {"type": "integer"}}},
    },
    "timeline": {
        "description": "Full temporal history for a subject (+optional predicate).",
        "inputSchema": {"type": "object", "required": ["subject"],
                        "properties": {"subject": {"type": "string"},
                                       "predicate": {"type": "string"}}},
    },
    "explain": {
        "description": "Provenance genealogy / decision evidence for an object id.",
        "inputSchema": {"type": "object", "required": ["id"],
                        "properties": {"id": {"type": "string"}}},
    },
    "record_decision": {
        "description": "Record a decision with supporting evidence ids.",
        "inputSchema": {"type": "object", "required": ["statement"],
                        "properties": {"statement": {"type": "string"},
                                       "evidence": {"type": "array", "items": {"type": "string"}}}},
    },
    "health": {"description": "Store health for the caller's scope.",
               "inputSchema": {"type": "object", "properties": {}}},
    "epistemos_context": {
        "description": "Build an EPCTX/1 context document (typed objects, contradictions, "
                       "completeness, temporal, provenance, token accounting). Identity is "
                       "server-side; arguments carry no authority.",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": ["string", "null"]},
            "intent": {"type": "string"},
            "as_of": {"type": "string"},
            "requested_budget": {"type": "integer"},
            "consumer_profile": {"type": "object"},
        }},
    },
    "epistemos_context_expand": {
        "description": "Redeem an opaque EPCTX expansion handle (experimental). Re-authorized live "
                       "for the caller; a stale/revoked/foreign handle returns nothing private.",
        "inputSchema": {"type": "object", "required": ["handle"],
                        "properties": {"handle": {"type": "string"}}},
    },
}


class MCPServer:
    def __init__(self, engine: Engine, principal: Principal, *,
                 tool_fn: Callable[..., Any] = _tool) -> None:
        self.engine = engine
        self.principal = principal  # server-side identity; clients cannot change it
        self._tool_fn = tool_fn

    # -- JSON-RPC dispatch ---------------------------------------------------
    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        rpc_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if method is None:
            return self._error(rpc_id, -32600, "invalid request")
        if method == "initialize":
            return self._ok(rpc_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "epistemos", "version": "0.1.0"},
            })
        if method in ("notifications/initialized", "initialized"):
            return None  # notification, no response
        if method == "tools/list":
            return self._ok(rpc_id, {"tools": [
                {"name": n, "description": t["description"], "inputSchema": t["inputSchema"]}
                for n, t in TOOLS.items()
            ]})
        if method == "tools/call":
            return self._call_tool(rpc_id, params)
        return self._error(rpc_id, -32601, f"method not found: {method}")

    def _call_tool(self, rpc_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        args = params.get("arguments") or {}
        if name not in TOOLS:
            return self._error(rpc_id, -32602, f"unknown tool: {name!r}")
        if not isinstance(args, dict):
            return self._error(rpc_id, -32602, "arguments must be an object")
        try:
            result = self._tool_fn(self.engine, self.principal, name, args)
        except KeyError as exc:
            # missing required argument -> tool error, not a protocol crash
            return self._tool_error(rpc_id, f"missing/unknown field: {exc}")
        except (ValueError, TypeError) as exc:
            # client-controlled argument of the wrong type (e.g. confidence="abc" -> float())
            # must be a tool error, not an uncaught exception that kills serve_stdio (B-03).
            return self._tool_error(rpc_id, f"invalid argument: {exc}")
        except EpistemosError as exc:
            return self._tool_error(rpc_id, f"{type(exc).__name__}: {exc}")
        return self._ok(rpc_id, {
            "content": [{"type": "text", "text": json.dumps(result)}],
            "isError": False,
        })

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _ok(rpc_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}

    @staticmethod
    def _error(rpc_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}

    def _tool_error(self, rpc_id: Any, message: str) -> dict[str, Any]:
        return self._ok(rpc_id, {"content": [{"type": "text", "text": message}], "isError": True})

    # -- stdio transport -----------------------------------------------------
    def serve_stdio(self, stdin: Any = None, stdout: Any = None) -> None:  # pragma: no cover
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                continue
            response = self.handle(request)
            if response is not None:
                stdout.write(json.dumps(response) + "\n")
                stdout.flush()
