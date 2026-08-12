"""EPISTEMOS-08 mutation gate for the promoted Context Envelope (§36).

Each mutation is a *non-equivalent* change to a critical guard in ``context/builder.py``. A mutation
that the context test suite still passes = ``NON_EQUIVALENT_SURVIVED`` — a hole in the tests. Gate:
``NON_EQUIVALENT_SURVIVED == 0``.

Mutations (the invariants the mission names):
  M1 contradiction-pin removed          — pinning disabled
  M2 history misclassified              — always collapse history regardless of intent
  M3 private-contradiction authz removed— attached contradiction not re-authorized (is_readable)
  M4 provenance dropped                 — dup detection disabled, folded ids lost
  M5 context_incomplete forced false    — never declare incompleteness
  M6 duplicate/corroboration confused   — key on title (so corroboration collapses)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src/epistemos/context/builder.py"

MUTATIONS = [
    ("M1 pin-removed",
     "contra_objs = self._contradictions(principal, objs) if cfg.pin_contradictions else []",
     "contra_objs = []  # MUT never pin"),
    ("M2 history-misclassified",
     "def _may_collapse_history(intent: str, confidence: str) -> bool:",
     "def _may_collapse_history(intent: str, confidence: str) -> bool:\n    return True  # MUT"),
    ("M3 attached-contradiction-authz-removed",
     "if ev is not None and self._eng.is_readable(principal, ev):",
     "if ev is not None:"),
    ("M4 provenance-dropped",
     "def _content_key(o: dict[str, Any]) -> str | None:",
     "def _content_key(o: dict[str, Any]) -> str | None:\n    return None  # MUT no dup"),
    ("M5 incomplete-forced-false",
     "context_incomplete=incomplete, incomplete_reasons=sorted(set(reasons)),",
     "context_incomplete=False, incomplete_reasons=[],  # MUT"),
    ("M6 dup-corroboration-confused",
     '    h = o.get("content_hash")',
     '    h = o.get("content_hash") or o.get("title")  # MUT collapse by title'),
]


def run_suite() -> bool:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/context/test_context.py", "-q", "-x",
         "--no-header", "-p", "no:cacheprovider"],
        cwd=SRC.parents[3], capture_output=True, text=True,
    )
    return r.returncode == 0


def main() -> None:
    original = SRC.read_text()
    assert run_suite(), "baseline suite must be green before mutation"
    survived: list[str] = []
    for name, old, new in MUTATIONS:
        if old not in original:
            print(f"  SKIP {name}: anchor not found")
            survived.append(name + " (anchor)")
            continue
        SRC.write_text(original.replace(old, new, 1))
        try:
            killed = not run_suite()
        finally:
            SRC.write_text(original)
        print(f"  {'KILLED ' if killed else 'SURVIVED'} {name}")
        if not killed:
            survived.append(name)
    assert SRC.read_text() == original, "source not restored!"
    print(f"\nNON_EQUIVALENT_SURVIVED = {len(survived)}")
    print("EPISTEMOS_08_MUTATION = " + ("PASS" if not survived else f"FAIL {survived}"))


if __name__ == "__main__":
    main()
