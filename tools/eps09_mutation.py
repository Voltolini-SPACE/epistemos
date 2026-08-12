"""EPISTEMOS-09 mutation gate for the EPCTX protocol (§32).

Each mutation breaks a guarantee the protocol makes. A mutation the protocol test suite still passes
is a hole (``NON_EQUIVALENT_SURVIVED``). Gate: ``NON_EQUIVALENT_SURVIVED == 0``.

  M1 claim-type-swap          — claim projected as fact (claim vs fact confusion, §24)
  M2 contradictions-removed   — contradiction section never populated (§8)
  M3 incomplete-forced-false  — completeness always 'complete' (§7)
  M4 temporal-marker-removed  — is_current always true (§9)
  M5 provenance-removed       — evidence refs stripped (§10)
  M6 expansion-binding-removed— handle no longer bound to its principal (§21, §22)
  M7 integrity-constant       — context_hash ignores content (§6)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIRE = ROOT / "src/epistemos/protocol/wire.py"
HANDLES = ROOT / "src/epistemos/protocol/handles.py"
SERIALIZE = ROOT / "src/epistemos/protocol/serialize.py"

MUTATIONS = [
    (WIRE, "M1 claim-type-swap",
     '    "fact": "fact", "claim": "claim", "evidence": "evidence",',
     '    "fact": "fact", "claim": "fact", "evidence": "evidence",'),
    (WIRE, "M2 contradictions-removed",
     "    contradiction_ids = set(env.pinned_contradictions)",
     "    contradiction_ids = set()  # MUT"),
    (WIRE, "M3 incomplete-forced-false",
     '            "complete": not env.context_incomplete,',
     '            "complete": True,  # MUT'),
    (WIRE, "M4 temporal-marker-removed",
     "def _is_current(obj: dict[str, Any]) -> bool:",
     "def _is_current(obj: dict[str, Any]) -> bool:\n    return True  # MUT"),
    (WIRE, "M5 provenance-removed",
     '    evidence_refs = [e for e in (obj.get("evidence") or []) if isinstance(e, str)]',
     "    evidence_refs = []  # MUT"),
    (HANDLES, "M6 expansion-binding-removed",
     "    if h is None or h.fingerprint != fp or h.tenant != principal.tenant:",
     "    if h is None:  # MUT"),
    (SERIALIZE, "M7 integrity-constant",
     "    digest = hashlib.sha256(canonical_bytes(body)).hexdigest()",
     '    digest = "constant"  # MUT'),
]


def run_suite() -> bool:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/protocol", "-q", "-x", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return r.returncode == 0


def main() -> None:
    originals = {p: p.read_text() for p in {WIRE, HANDLES, SERIALIZE}}
    assert run_suite(), "baseline protocol suite must be green before mutation"
    survived: list[str] = []
    for path, name, old, new in MUTATIONS:
        src = originals[path]
        if old not in src:
            print(f"  SKIP {name}: anchor not found")
            survived.append(name + " (anchor)")
            continue
        path.write_text(src.replace(old, new, 1))
        try:
            killed = not run_suite()
        finally:
            path.write_text(src)
        print(f"  {'KILLED ' if killed else 'SURVIVED'} {name}")
        if not killed:
            survived.append(name)
    for p, s in originals.items():
        assert p.read_text() == s, f"{p} not restored!"
    print(f"\nNON_EQUIVALENT_SURVIVED = {len(survived)}")
    print("EPISTEMOS_09_MUTATION = " + ("PASS" if not survived else f"FAIL {survived}"))


if __name__ == "__main__":
    main()
