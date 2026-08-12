"""Targeted mutation harness for the EPISTEMOS **Panel boundaries** hardened in
EPISTEMOS-PANEL-HARDENING-01. Same method as tools/mutation_harness.py — copy the package, apply
one source mutation, run the panel invariant suite against the copy, classify by pytest exit code
(0=SURVIVED coverage gap, 1=KILLED). Each mutant reopens a hole this mission closed.

Run: `python tools/mutation_panel.py`.  Critical gate: SURVIVED == 0.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "epistemos"
TEST_TARGETS = ["tests/panel"]

# id, file (rel to src/epistemos), find, replace, boundary, note
MUTANTS = [
    ("asof_include_future_events", "api/panel.py",
     "        if str(rec.ts) > at_tx:\n            continue",
     "        if False:\n            continue",
     "bitemporal", "as_of reconstructs state from events with ts<=at_tx (FUTURE_KNOWLEDGE_LEAK=0)"),
    ("asof_status_ignore_retraction", "api/panel.py",
     "            elif oid in asof.retracted:\n                node[\"status\"] = \"retracted\"",
     "            elif False:\n                node[\"status\"] = \"retracted\"",
     "bitemporal", "a retracted claim reads 'retracted' once at_tx passes the retraction"),
    ("readmodel_drop_firewall", "api/panel.py",
     "            if k in want and eng.is_readable(principal, o):",
     "            if k in want:",
     "read-firewall", "single-pass read-model still gates every object on is_readable"),
    ("qint_swallow_bad_value", "api/server.py",
     "        except (TypeError, ValueError) as exc:\n"
     "            raise ValidationError(f\"parameter {key!r} must be an integer\") from exc",
     "        except (TypeError, ValueError):\n            return default",
     "validation", "malformed int param -> 400, not a silently-defaulted 200 (F1)"),
    ("qreq_return_empty_not_raise", "api/server.py",
     "        if val is None or val == \"\":\n"
     "            raise ValidationError(f\"missing required parameter {key!r}\")",
     "        if val is None or val == \"\":\n            return \"\"",
     "validation", "missing required param -> 400, never a blank-id lookup (F1)"),
    ("post_skip_body_drain", "api/server.py",
     "            if not self._body_consumed and not self.close_connection:\n"
     "                self._drain_body()",
     "            if False:\n                self._drain_body()",
     "request-smuggling", "errored POST body is drained so it cannot be smuggled (F3)"),
    ("fail_leak_5xx_message", "api/server.py",
     "        msg = str(exc) if code in _DETAILED_ERROR else _SAFE_ERROR.get(code, \"error\")",
     "        msg = str(exc)",
     "info-leak", "5xx responses use a generic message, never str(exc) internals (F1)"),
    ("server_version_leak_python", "api/server.py",
     "    def version_string(self) -> str:\n"
     "        # do not advertise the Python runtime version in the Server header (fingerprinting)\n"
     "        return self.server_version",
     "    def version_string(self) -> str:\n        return self.server_version + \" leakcheck\"",
     "fingerprinting", "Server header must not advertise the Python version (F4)"),
    ("stream_drop_isreadable", "api/stream.py",
     "        if obj is None or not engine.is_readable(principal, obj):",
     "        if obj is None:",
     "stream-firewall", "SSE/activity events gated on is_readable (PRIVATE_STREAM_LEAK=0)"),
]


def run_suite(pkg_parent: Path) -> int:
    import os

    env = {**os.environ, "PYTHONPATH": str(pkg_parent)}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TEST_TARGETS, "-q", "-x", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=300,
    )
    return proc.returncode


def apply_mutant(find: str, replace: str, rel: str, dest_pkg: Path) -> bool:
    target = dest_pkg / rel
    text = target.read_text()
    if find not in text:
        return False
    target.write_text(text.replace(find, replace, 1))
    return True


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        parent = Path(d)
        shutil.copytree(SRC, parent / "epistemos")
        control_rc = run_suite(parent)
    if control_rc != 0:
        print(f"CONTROL FAILED (rc={control_rc}) — aborting")
        return 3
    print(f"CONTROL rc={control_rc} (green baseline)\n")

    results = []
    for mut_id, rel, find, replace, boundary, note in MUTANTS:
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            dest = parent / "epistemos"
            shutil.copytree(SRC, dest)
            if not apply_mutant(find, replace, rel, dest):
                results.append((mut_id, boundary, "INVALID", note))
                print(f"  {'INVALID':9} {mut_id:30} (snippet not found)")
                continue
            rc = run_suite(parent)
        status = {0: "SURVIVED", 1: "KILLED"}.get(rc, "INVALID")
        results.append((mut_id, boundary, status, note))
        print(f"  {status:9} {mut_id:30} ({boundary}) — {note}")

    killed = sum(1 for r in results if r[2] == "KILLED")
    survived = sum(1 for r in results if r[2] == "SURVIVED")
    invalid = sum(1 for r in results if r[2] == "INVALID")
    print(f"\nTOTAL={len(results)} KILLED={killed} SURVIVED={survived} INVALID={invalid}")
    print("PANEL_MUTATION_CRITICAL = " + ("PASS" if survived == 0 and invalid == 0 else "FAIL"))
    return 0 if survived == 0 and invalid == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
