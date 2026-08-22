"""``epistemos`` — the installed command-line entry point.

A thin, explicit dispatcher over the surfaces that already exist. It adds no capability of its
own: every subcommand is a documented way to reach the Panel, the REST boundary, the MCP server
or the integrity verifier. Nothing here bypasses authorization — every server is constructed with
an explicit principal or token map, exactly as the library requires.

Local-first and zero-egress hold at this layer too: servers bind ``127.0.0.1`` by default and the
verifier reads a local file. No subcommand contacts the network.
"""

from __future__ import annotations

import argparse
import errno
import json
import sys
from collections.abc import Sequence
from typing import Any

__all__ = ["main"]

_PROG = "epistemos"


def _version() -> str:
    from . import __version__  # noqa: PLC0415

    return str(__version__)


def _bind_error(host: str, port: int, exc: OSError, *, retry_hint: str) -> int:
    """Turn a raw socket bind failure into an actionable message (never a traceback)."""
    if exc.errno == errno.EADDRINUSE:
        sys.stderr.write(
            f"error: {host}:{port} is already in use.\n"
            f"       Another process is listening there — stop it, or pick a free port:\n"
            f"         {retry_hint}\n"
        )
    elif exc.errno in (errno.EACCES, errno.EPERM):
        sys.stderr.write(
            f"error: not allowed to bind {host}:{port}.\n"
            f"       Ports below 1024 need elevated privileges — pick a higher port.\n"
        )
    elif exc.errno == errno.EADDRNOTAVAIL:
        sys.stderr.write(
            f"error: {host} is not an address on this machine.\n"
            f"       Use --host 127.0.0.1 to serve locally.\n"
        )
    else:
        sys.stderr.write(f"error: could not bind {host}:{port} — {exc}\n")
    return 2


# ---------------------------------------------------------------------------
# subcommands


def _cmd_panel(args: argparse.Namespace, rest: list[str]) -> int:
    """Delegate verbatim to the Panel entry point so there is exactly one implementation."""
    from .panel.__main__ import main as panel_main  # noqa: PLC0415

    return panel_main(rest)


def _cmd_serve(args: argparse.Namespace, rest: list[str]) -> int:
    from .api.rest import make_server  # noqa: PLC0415
    from .core import Engine  # noqa: PLC0415

    tokens = _parse_tokens(args.token, tenant=args.tenant, namespace=args.namespace)
    if not tokens:
        sys.stderr.write(
            "error: serve requires at least one --token TOKEN=AGENT pair.\n"
            "       The REST boundary never serves unauthenticated reads.\n"
            f"       example: {_PROG} serve --db knowledge.epistemos --token s3cret=claude\n"
        )
        return 2
    engine = Engine.open(args.db)
    try:
        server = make_server(engine, host=args.host, port=args.port, tokens=tokens)
    except OSError as exc:
        engine.close()
        return _bind_error(
            args.host, args.port, exc,
            retry_hint=f"{_PROG} serve --db {args.db} --port {args.port + 1} ...",
        )
    host, port = str(server.server_address[0]), int(server.server_address[1])
    sys.stdout.write(f"EPISTEMOS REST — http://{host}:{port}/  (local-first, zero-egress)\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\nshutting down\n")
    finally:
        server.server_close()
        engine.close()
    return 0


def _cmd_mcp(args: argparse.Namespace, rest: list[str]) -> int:
    """Serve the fixed MCP tool registry over stdio (the transport MCP clients expect)."""
    from .core import Engine  # noqa: PLC0415
    from .identity import Principal  # noqa: PLC0415
    from .mcp import MCPServer  # noqa: PLC0415

    engine = Engine.open(args.db)
    # Identity is fixed here, server-side. Tool arguments can never choose tenant or namespace.
    principal = Principal(tenant=args.tenant, agent=args.agent, namespace=args.namespace)
    try:
        MCPServer(engine, principal).serve_stdio()
    except KeyboardInterrupt:
        pass
    finally:
        engine.close()
    return 0


def _cmd_compile(args: argparse.Namespace, rest: list[str]) -> int:
    """Compile a text file into candidate claims. Nothing here becomes accepted knowledge."""
    from pathlib import Path  # noqa: PLC0415

    from .core import Engine  # noqa: PLC0415
    from .identity import Principal  # noqa: PLC0415
    from .ingest import compile_text  # noqa: PLC0415

    path = Path(args.file)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"error: cannot read {args.file} — {exc.strerror or exc}\n")
        return 2
    except UnicodeDecodeError:
        sys.stderr.write(
            f"error: {args.file} is not UTF-8 text.\n"
            f"       The compiler reads text; convert or extract it first.\n"
        )
        return 2

    title = args.title or path.stem

    if args.dry_run:
        # Show what *would* be proposed, without writing anything. Inspecting before committing
        # is the point: these are candidates, and a wrong one indicts a named rule.
        extractions = compile_text(text, subject=title)
        if args.json:
            sys.stdout.write(json.dumps([
                {"subject": e.subject, "predicate": e.predicate, "object": e.object,
                 "rule": e.rule, "confidence": e.confidence,
                 "span": [e.span.start, e.span.end], "quote": e.span.text(text)}
                for e in extractions
            ], indent=2, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(f"{len(extractions)} candidate claim(s) from {args.file} "
                             f"— dry run, nothing written\n\n")
            for e in extractions:
                obj = f" -> {e.object}" if e.object else ""
                sys.stdout.write(f"  [{e.rule} {e.confidence:.2f}] "
                                 f"({e.subject}, {e.predicate}{obj})\n")
                sys.stdout.write(f"      {e.span.text(text)!r}\n")
        return 0

    engine = Engine.open(args.db)
    principal = Principal(tenant=args.tenant, agent=args.agent, namespace=args.namespace)
    try:
        # A file path names one document, so re-running this command on unchanged content must
        # reuse the document rather than ingest a near-duplicate — otherwise every run would
        # produce a fresh document id, defeat the content-keyed dedupe, and silently multiply
        # the same claims. Identity is the content hash the Engine already stores.
        digest = Engine.document_content_hash(title=title, text=text)
        existing = next(
            (obj for obj in engine.store.objects(args.tenant, args.namespace, "document")
             if obj.get("source_hash") == digest),
            None,
        )
        reused = existing is not None
        doc_id = str(existing["id"]) if existing else engine.ingest_document(
            principal, title=title, text=text
        ).id
        result = engine.compile_document(principal, document=doc_id, space=args.space)
    finally:
        engine.close()

    if args.json:
        sys.stdout.write(json.dumps({
            "document": result.document,
            "document_reused": reused,
            "created": result.created,
            "skipped": len(result.skipped),
            "by_rule": result.by_rule,
            "claims": [{"id": c.id, "subject": c.subject, "predicate": c.predicate,
                        "object": c.object, "confidence": c.confidence} for c in result.claims],
        }, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(f"document   {result.document}"
                         f"{'  (unchanged, reused)' if reused else ''}\n")
        sys.stdout.write(f"created    {result.created} candidate claim(s)\n")
        sys.stdout.write(f"skipped    {len(result.skipped)} (already compiled)\n")
        for rule, count in result.by_rule.items():
            sys.stdout.write(f"  {rule:20s} {count}\n")
        sys.stdout.write("\nThese are PROPOSED claims, not accepted knowledge — belief stays\n"
                         "derived and acceptance stays governed. Review them before relying on\n"
                         "them; each one quotes the span it came from.\n")
    return 0


def _cmd_verify(args: argparse.Namespace, rest: list[str]) -> int:
    """Verify the hash chain and (when indexed) index consistency. Exit 1 on any failure."""
    from .core import Engine  # noqa: PLC0415
    from .errors import EpistemosError  # noqa: PLC0415

    engine = Engine.open(args.db)
    report: dict[str, Any] = {"target": args.db}
    try:
        try:
            report["events_verified"] = engine.verify_integrity(
                expected_count=args.expect_count, expected_head=args.expect_head
            )
            report["ledger"] = "OK"
        except EpistemosError as exc:
            report["ledger"] = "FAILED"
            report["ledger_error"] = str(exc)

        try:
            report["index_consistent"] = engine.verify_index_consistency()
        except EpistemosError as exc:
            report["index_consistent"] = False
            report["index_error"] = str(exc)
    finally:
        engine.close()

    ok = report.get("ledger") == "OK" and report.get("index_consistent") is not False
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"target            {report['target']}\n")
        sys.stdout.write(f"ledger            {report['ledger']}\n")
        if "events_verified" in report:
            sys.stdout.write(f"events verified   {report['events_verified']}\n")
        if "ledger_error" in report:
            sys.stdout.write(f"ledger error      {report['ledger_error']}\n")
        sys.stdout.write(f"index consistent  {report.get('index_consistent')}\n")
        if "index_error" in report:
            sys.stdout.write(f"index error       {report['index_error']}\n")
        sys.stdout.write(f"\n{'VERIFY OK' if ok else 'VERIFY FAILED'}\n")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# helpers


def _parse_tokens(pairs: Sequence[str] | None, *, tenant: str, namespace: str) -> dict[str, Any]:
    from .identity import Principal  # noqa: PLC0415

    out: dict[str, Any] = {}
    for pair in pairs or ():
        if "=" not in pair:
            sys.stderr.write(f"error: --token expects TOKEN=AGENT, got {pair!r}\n")
            continue
        token, agent = pair.split("=", 1)
        token, agent = token.strip(), agent.strip()
        if token and agent:
            out[token] = Principal(tenant=tenant, agent=agent, namespace=namespace)
    return out


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=_PROG,
        description="Sovereign context, memory, provenance and decision-lineage engine. "
                    "Local-first; no subcommand contacts the network.",
    )
    ap.add_argument("--version", action="version", version=f"{_PROG} {_version()}")
    sub = ap.add_subparsers(dest="command", metavar="COMMAND")

    p_panel = sub.add_parser(
        "panel", help="open the read-only Panel in a browser (accepts the panel flags verbatim)",
        add_help=False,
    )
    p_panel.set_defaults(func=_cmd_panel, passthrough=True)

    p_serve = sub.add_parser("serve", help="serve the authorized REST read model on localhost")
    p_serve.add_argument("--db", default=None,
                         help="path to a .epistemos file (default: in-memory)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8788)
    p_serve.add_argument("--token", action="append", metavar="TOKEN=AGENT",
                         help="grant a bearer token to an agent (repeatable, required)")
    p_serve.add_argument("--tenant", default="default")
    p_serve.add_argument("--namespace", default="kb")
    p_serve.set_defaults(func=_cmd_serve, passthrough=False)

    p_mcp = sub.add_parser("mcp", help="serve the MCP tool registry over stdio")
    p_mcp.add_argument("--db", default=None, help="path to a .epistemos file (default: in-memory)")
    p_mcp.add_argument("--tenant", default="default")
    p_mcp.add_argument("--agent", default="mcp")
    p_mcp.add_argument("--namespace", default="kb")
    p_mcp.set_defaults(func=_cmd_mcp, passthrough=False)

    p_compile = sub.add_parser(
        "compile",
        help="compile a text file into candidate claims (deterministic, no model)",
    )
    p_compile.add_argument("file", help="UTF-8 text or Markdown file to compile")
    p_compile.add_argument("--db", default=None, help="path to a .epistemos file")
    p_compile.add_argument("--title", default=None,
                           help="document title (defaults to the file name)")
    p_compile.add_argument("--space", default=None, help="knowledge space for the claims")
    p_compile.add_argument("--tenant", default="default")
    p_compile.add_argument("--agent", default="compiler")
    p_compile.add_argument("--namespace", default="kb")
    p_compile.add_argument("--dry-run", action="store_true",
                           help="show what would be proposed; write nothing")
    p_compile.add_argument("--json", action="store_true", help="emit the result as JSON")
    p_compile.set_defaults(func=_cmd_compile, passthrough=False)

    p_verify = sub.add_parser("verify", help="verify the hash chain and index consistency")
    p_verify.add_argument("db", help="path to a .epistemos file")
    p_verify.add_argument("--expect-count", type=int, default=None,
                          help="anchored event count, to detect tail truncation")
    p_verify.add_argument("--expect-head", default=None,
                          help="anchored head hash, to detect a full re-chained rewrite")
    p_verify.add_argument("--json", action="store_true", help="emit the report as JSON")
    p_verify.set_defaults(func=_cmd_verify, passthrough=False)

    return ap


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = _build_parser()

    # `panel` forwards its own flags (including --help) to the Panel parser untouched.
    if argv and argv[0] == "panel":
        from .panel.__main__ import main as panel_main  # noqa: PLC0415

        return panel_main(argv[1:])

    args = ap.parse_args(argv)
    if getattr(args, "command", None) is None:
        ap.print_help()
        return 0
    return int(args.func(args, []))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
