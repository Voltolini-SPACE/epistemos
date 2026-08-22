"""The installed ``epistemos`` command-line boundary.

The CLI adds no capability of its own, so these tests assert the two things that could go wrong
at this layer: that it never *widens* authorization (serve refuses to run unauthenticated, mcp
fixes identity server-side), and that operational failures surface as actionable messages with a
non-zero exit code rather than as a traceback.
"""

from __future__ import annotations

import errno
import json
import socket

import pytest

from epistemos import Engine, Principal
from epistemos.cli import main

pytestmark = pytest.mark.integration


# -- surface ----------------------------------------------------------------


def test_no_args_prints_help_and_succeeds(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "usage: epistemos" in out
    for command in ("panel", "serve", "mcp", "verify"):
        assert command in out


def test_version_matches_the_package(capsys):
    from epistemos import __version__

    with pytest.raises(SystemExit) as exc:  # argparse's --version exits
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


# -- verify -----------------------------------------------------------------


def _seed(path: str) -> None:
    eng = Engine.open(path)
    ctx = Principal(tenant="acme", agent="claude", namespace="hr")
    src = eng.add_source(ctx, uri="mem://note", trust=0.6)
    eng.assert_fact(ctx, subject="Alice", predicate="works_at", object="Acme", source=src.id)
    eng.close()


def test_verify_reports_ok_on_an_intact_store(tmp_path, capsys):
    db = str(tmp_path / "kb.epistemos")
    _seed(db)
    assert main(["verify", db]) == 0
    out = capsys.readouterr().out
    assert "VERIFY OK" in out
    assert "ledger            OK" in out


def test_verify_json_is_machine_readable(tmp_path, capsys):
    db = str(tmp_path / "kb.epistemos")
    _seed(db)
    assert main(["verify", db, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ledger"] == "OK"
    assert report["events_verified"] >= 1
    assert report["index_consistent"] is True


def test_verify_exits_nonzero_when_the_anchor_disagrees(tmp_path, capsys):
    """A wrong anchored count is exactly the tail-truncation signal; it must fail, not warn."""
    db = str(tmp_path / "kb.epistemos")
    _seed(db)
    assert main(["verify", db, "--expect-count", "99999"]) == 1
    out = capsys.readouterr().out
    assert "VERIFY FAILED" in out
    assert "ledger            FAILED" in out


# -- serve: authorization is never widened by the CLI -----------------------


def test_serve_refuses_to_start_without_a_token(capsys):
    """The REST boundary never serves unauthenticated reads — the CLI must not offer a way in."""
    assert main(["serve", "--port", "0"]) == 2
    err = capsys.readouterr().err
    assert "requires at least one --token" in err
    assert "Traceback" not in err


def test_serve_rejects_a_malformed_token_pair(capsys):
    assert main(["serve", "--port", "0", "--token", "no-equals-sign"]) == 2
    err = capsys.readouterr().err
    assert "TOKEN=AGENT" in err


# -- operational failures are messages, not tracebacks ----------------------


def test_port_already_in_use_is_an_actionable_message(capsys):
    """Regression guard: this used to raise a raw socketserver traceback (OSError 48)."""
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    port = holder.getsockname()[1]
    try:
        code = main(["serve", "--port", str(port), "--token", "s3cret=claude"])
    finally:
        holder.close()

    captured = capsys.readouterr()
    assert code == 2
    assert "already in use" in captured.err
    assert str(port) in captured.err
    assert "Traceback" not in captured.err


def test_bind_error_helper_covers_the_documented_errnos(capsys):
    from epistemos.cli import _bind_error

    cases = {
        errno.EADDRINUSE: "already in use",
        errno.EACCES: "not allowed to bind",
        errno.EADDRNOTAVAIL: "not an address on this machine",
        errno.ENOBUFS: "could not bind",
    }
    for code, expected in cases.items():
        assert _bind_error("127.0.0.1", 8787, OSError(code, "x"), retry_hint="hint") == 2
        assert expected in capsys.readouterr().err


# -- panel passthrough -------------------------------------------------------


def test_panel_subcommand_forwards_argv_verbatim(monkeypatch):
    """`epistemos panel` must not re-parse the Panel's flags — there is one implementation."""
    seen: list[list[str]] = []

    def fake_panel_main(argv):
        seen.append(list(argv))
        return 0

    import epistemos.panel.__main__ as panel_main_mod

    monkeypatch.setattr(panel_main_mod, "main", fake_panel_main)
    assert main(["panel", "--demo", "--port", "8899", "--live-demo"]) == 0
    assert seen == [["--demo", "--port", "8899", "--live-demo"]]


def test_panel_db_without_tokens_fails_closed(tmp_path, capsys):
    """A persisted Panel store has no demo identities, so it must refuse to serve anonymously."""
    db = str(tmp_path / "kb.epistemos")
    _seed(db)
    monkey = pytest.MonkeyPatch()
    monkey.delenv("EPISTEMOS_PANEL_TOKENS", raising=False)
    try:
        assert main(["panel", "--db", db, "--port", "0"]) == 2
    finally:
        monkey.undo()
    assert "EPISTEMOS_PANEL_TOKENS" in capsys.readouterr().err
