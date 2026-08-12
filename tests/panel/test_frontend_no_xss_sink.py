"""Structural XSS guard for the panel frontend (EPISTEMOS-PANEL-HARDENING-01, §6).

Claims/evidence/reviews/sources carry user-controlled content. The vanilla frontend renders it
exclusively through ``textContent`` / text-node children (never ``innerHTML``), so a payload can
only ever appear as inert text — proven live in the browser, and pinned here so a future edit
cannot silently reintroduce an HTML sink. The strict CSP (``script-src 'self'``) is the second
layer; this test defends the first.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WEB = Path(__file__).resolve().parents[2] / "src" / "epistemos" / "panel" / "web"

# sinks that turn a string into live DOM/JS — none may appear in the panel's own scripts
_FORBIDDEN = [
    r"\.innerHTML\b",
    r"\.outerHTML\b",
    r"insertAdjacentHTML",
    r"document\.write",
    r"\beval\s*\(",
    r"new\s+Function\s*\(",
    r"html:",  # the el() `html` prop was removed; its reappearance is a regression
]


def _js_files() -> list[Path]:
    files = sorted(_WEB.glob("*.js"))
    assert files, f"no panel JS found under {_WEB}"
    return files


@pytest.mark.parametrize("pattern", _FORBIDDEN)
def test_no_html_injection_sink_in_frontend(pattern):
    rx = re.compile(pattern)
    hits = []
    for f in _js_files():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if rx.search(line):
                hits.append(f"{f.name}:{i}: {line.strip()}")
    assert not hits, f"forbidden DOM/JS sink {pattern!r}:\n" + "\n".join(hits)


def test_el_helper_has_no_innerhtml_branch():
    dom = (_WEB / "dom.js").read_text(encoding="utf-8")
    assert "innerHTML" not in dom, "el() must not expose an innerHTML sink"
    assert "textContent" in dom, "el() must render text via textContent"
