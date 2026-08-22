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
import functools
import json
import re
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


@functools.lru_cache(maxsize=256)
def _glob_regex(pattern: str) -> re.Pattern[str]:
    """A relative-path glob with real globstar semantics, which `fnmatch` does not have.

    ``fnmatch`` translates ``**`` exactly like ``*``, so ``**/*.md`` demands a slash and silently
    skips every file at the walk root. Here ``**/`` matches zero or more directories, ``**``
    matches across slashes, and ``*``/``?`` stop at a slash — the semantics every glob user
    actually expects.
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def _glob_match(rel: str, pattern: str) -> bool:
    return _glob_regex(pattern).match(rel) is not None


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


def _cmd_ingest(args: argparse.Namespace, rest: list[str]) -> int:
    """Idempotent vault sync: compile every matching Markdown file under a directory.

    Deterministic walk, per-file fail-closed (one unreadable file is an ``error`` entry, never an
    aborted run), and idempotent by construction: an unchanged file reuses its document by
    content hash and re-proposes nothing; a changed file becomes a new document that records
    which one it supersedes. Everything produced is a PROPOSED claim, as everywhere else.
    """
    import os  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    from .core import Engine  # noqa: PLC0415
    from .errors import EpistemosError  # noqa: PLC0415
    from .identity import Principal  # noqa: PLC0415
    from .ingest import compile_text  # noqa: PLC0415
    from .ingest.markdown import MARKDOWN_RULES  # noqa: PLC0415

    base = Path(args.dir)
    if not base.is_dir():
        sys.stderr.write(f"error: {args.dir} is not a directory\n")
        return 2

    includes = args.include or ["**/*.md"]
    excludes = args.exclude or []

    def wanted(rel: str) -> bool:
        if any(part.startswith(".") for part in rel.split("/")):
            return False  # .obsidian, .git, dotfiles — never
        if not any(_glob_match(rel, g) for g in includes):
            return False
        return not any(_glob_match(rel, g) for g in excludes)

    def pruned(rel_dir: str) -> bool:
        """Skip whole subtrees an exclude names (`x/**`, `**/node_modules/**`) — the file-level
        filter would drop every file anyway; this just avoids walking a repo dump to do it."""
        return any(
            g.endswith("/**") and _glob_match(rel_dir, g[:-3]) for g in excludes
        )

    files: list[Path] = []
    for root, dirs, names in os.walk(base):
        rel_root = Path(root).relative_to(base).as_posix()
        dirs[:] = sorted(
            d for d in dirs
            if not d.startswith(".")
            and not pruned(d if rel_root == "." else f"{rel_root}/{d}")
        )
        for name in sorted(names):
            rel = name if rel_root == "." else f"{rel_root}/{name}"
            if wanted(rel):
                files.append(Path(root) / name)

    report: list[dict[str, Any]] = []
    by_rule_total: dict[str, int] = {}
    counts = {"new": 0, "unchanged": 0, "changed": 0, "error": 0}
    claims_created = 0
    claims_skipped = 0

    if args.dry_run:
        for path in files:
            rel = path.relative_to(base).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                counts["error"] += 1
                report.append({"path": rel, "status": "error", "error": str(exc)})
                continue
            extractions = compile_text(text, subject=path.stem, rules=MARKDOWN_RULES)
            for e in extractions:
                by_rule_total[e.rule] = by_rule_total.get(e.rule, 0) + 1
            report.append({"path": rel, "status": "would-compile",
                           "extractions": len(extractions)})
        summary: dict[str, Any] = {
            "directory": str(base), "files": len(files), "errors": counts["error"],
            "extractions": sum(r.get("extractions", 0) for r in report),
            "by_rule": dict(sorted(by_rule_total.items())), "dry_run": True,
        }
        if args.json:
            sys.stdout.write(json.dumps({"summary": summary, "files": report},
                                        indent=2, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(f"{summary['files']} file(s), "
                             f"{summary['extractions']} candidate claim(s) "
                             f"— dry run, nothing written\n")
            for rule, count in summary["by_rule"].items():
                sys.stdout.write(f"  {rule:20s} {count}\n")
        return 1 if counts["error"] else 0

    if args.db is None:
        sys.stderr.write("error: --db is required (ingest writes a database).\n"
                         "       Use --dry-run to preview without one.\n")
        return 2

    # Tokenizer: explicit wins; an existing database inherits its stored representation; a NEW
    # vault database defaults to "unicode" — an index that cannot match `Sessões` is the broken
    # outcome for the exact content this command exists to ingest.
    tokenizer = args.tokenizer
    if tokenizer is None and not Path(args.db).exists():
        tokenizer = "unicode"

    engine = Engine.open(args.db, tokenizer=tokenizer)
    principal = Principal(tenant=args.tenant, agent=args.agent, namespace=args.namespace)
    try:
        # One pre-scan, two maps — per-file rescans would be O(files x documents).
        by_hash: dict[str, dict[str, Any]] = {}
        by_path: dict[str, dict[str, Any]] = {}
        for obj in engine.store.objects(args.tenant, args.namespace, "document"):
            if obj.get("source_hash"):
                by_hash[str(obj["source_hash"])] = obj
            meta = obj.get("metadata")
            if isinstance(meta, dict) and meta.get("vault_path"):
                by_path[str(meta["vault_path"])] = obj
        # And one claims scan for the dedupe keys, carried across every file (mutated in place).
        known_keys = {
            str(obj.get("metadata", {}).get("compile_key"))
            for obj in engine.store.objects(args.tenant, args.namespace, "claim")
            if isinstance(obj.get("metadata"), dict) and obj["metadata"].get("compile_key")
        }

        for path in files:
            rel = path.relative_to(base).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                counts["error"] += 1
                report.append({"path": rel, "status": "error", "error": str(exc)})
                continue
            title = path.stem
            digest = Engine.document_content_hash(title=title, text=text,
                                                  mime="text/markdown")
            try:
                if digest in by_hash:
                    doc_id = str(by_hash[digest]["id"])
                    status = "unchanged"
                elif rel in by_path:
                    doc = engine.ingest_document(
                        principal, title=title, text=text, mime="text/markdown",
                        metadata={"vault_path": rel,
                                  "supersedes": str(by_path[rel]["id"])},
                    )
                    doc_id = doc.id
                    status = "changed"
                else:
                    doc = engine.ingest_document(
                        principal, title=title, text=text, mime="text/markdown",
                        metadata={"vault_path": rel},
                    )
                    doc_id = doc.id
                    status = "new"
                if status != "unchanged":
                    obj = {"id": doc_id, "source_hash": digest,
                           "metadata": {"vault_path": rel}}
                    by_hash[digest] = obj
                    by_path[rel] = obj
                # Unchanged files still compile — it heals a run interrupted between ingest and
                # compile, and costs nothing: every key is already in `known_keys`.
                result = engine.compile_document(
                    principal, document=doc_id, space=args.space,
                    rules=MARKDOWN_RULES, known_keys=known_keys,
                )
            except EpistemosError as exc:
                counts["error"] += 1
                report.append({"path": rel, "status": "error", "error": str(exc)})
                continue
            counts[status] += 1
            claims_created += result.created
            claims_skipped += len(result.skipped)
            for rule, count in result.by_rule.items():
                by_rule_total[rule] = by_rule_total.get(rule, 0) + count
            report.append({"path": rel, "status": status, "document": doc_id,
                           "created": result.created, "skipped": len(result.skipped)})
        tokenizer_name = engine.tokenizer.name
    finally:
        engine.close()

    summary = {
        "directory": str(base), "db": args.db, "tokenizer": tokenizer_name,
        "files": len(files), **counts,
        "claims_created": claims_created, "claims_skipped": claims_skipped,
        "by_rule": dict(sorted(by_rule_total.items())),
    }
    if args.json:
        sys.stdout.write(json.dumps({"summary": summary, "files": report},
                                    indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(f"{summary['files']} file(s): {counts['new']} new, "
                         f"{counts['unchanged']} unchanged, {counts['changed']} changed, "
                         f"{counts['error']} error(s)\n")
        sys.stdout.write(f"claims     {claims_created} created, "
                         f"{claims_skipped} already compiled\n")
        for rule, count in summary["by_rule"].items():
            sys.stdout.write(f"  {rule:20s} {count}\n")
        sys.stdout.write(f"index      tokenizer={tokenizer_name}\n")
        for entry in report:
            if entry["status"] == "error":
                sys.stdout.write(f"  ERROR {entry['path']}: {entry['error']}\n")
        sys.stdout.write("\nThese are PROPOSED claims, not accepted knowledge — belief stays\n"
                         "derived and acceptance stays governed. Re-running this command on an\n"
                         "unchanged vault creates nothing.\n")
    return 1 if counts["error"] else 0


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

    p_ingest = sub.add_parser(
        "ingest",
        help="idempotently compile a directory of Markdown files (an Obsidian-style vault)",
    )
    p_ingest.add_argument("dir", help="directory to walk for Markdown files")
    p_ingest.add_argument("--db", default=None, help="path to a .epistemos file")
    p_ingest.add_argument("--include", action="append", metavar="GLOB",
                          help="relative-path glob to include (repeatable; default **/*.md)")
    p_ingest.add_argument("--exclude", action="append", metavar="GLOB",
                          help="relative-path glob to exclude (repeatable); dot-directories "
                               "are always excluded")
    p_ingest.add_argument("--tokenizer", choices=["ascii", "unicode", "plural"], default=None,
                          help="index tokenizer; default: inherit from the database, or "
                               "'unicode' when creating a new one")
    p_ingest.add_argument("--space", default=None, help="knowledge space for the claims")
    p_ingest.add_argument("--tenant", default="default")
    p_ingest.add_argument("--agent", default="compiler")
    p_ingest.add_argument("--namespace", default="kb")
    p_ingest.add_argument("--dry-run", action="store_true",
                          help="walk and compile, write nothing")
    p_ingest.add_argument("--json", action="store_true", help="emit the report as JSON")
    p_ingest.set_defaults(func=_cmd_ingest, passthrough=False)

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
