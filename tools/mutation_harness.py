"""Targeted mutation harness for EPISTEMOS critical boundaries (mission §32, checkpoint AD).

Off-the-shelf mutation tools do not reliably support Python 3.14, so this is the mission's
sanctioned *targeted* fallback: for each hand-picked mutation of a critical predicate, copy the
package, apply one source edit, and run the invariant test suite against the copy.

Classification is by pytest **exit code** (never by the word "error" in output — a known trap):
  0 -> SURVIVED (tests still pass with the bug in place = a coverage gap)
  1 -> KILLED   (a test failed = the boundary is protected)
  2..5 -> INVALID (collection/usage error = mutation didn't compile/collect)

Critical gate: NON_EQUIVALENT_SURVIVED == 0. Run: `python tools/mutation_harness.py`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "epistemos"
# invariant tests to run against each mutant (fast; excludes env-specific source-check)
TEST_TARGETS = ["tests/unit", "tests/security", "tests/index", "tests/spaces", "tests/claims"]
IGNORE = ["--ignore=tests/unit/test_source_check.py"]

# id, file (relative to src/epistemos), find, replace, boundary, note
MUTANTS = [
    ("temporal_lower_ge_to_gt", "temporal/__init__.py",
     "after_lo = lo_dt is None or instant >= lo_dt",
     "after_lo = lo_dt is None or instant > lo_dt",
     "temporal", "valid-time lower bound inclusion"),
    ("temporal_upper_lt_to_le", "temporal/__init__.py",
     "before_hi = hi_dt is None or instant < hi_dt",
     "before_hi = hi_dt is None or instant <= hi_dt",
     "temporal", "valid-time upper bound exclusion (half-open)"),
    ("ledger_skip_content_hash", "ledger/__init__.py",
     "if recomputed_content != rec.content_hash:",
     "if False:",
     "ledger", "payload tamper detection"),
    ("ledger_skip_prev_link", "ledger/__init__.py",
     "if rec.prev_hash != prev:",
     "if False:",
     "ledger", "chain-break detection"),
    ("ledger_skip_seq_check", "ledger/__init__.py",
     "if rec.seq != expected_seq:",
     "if False:",
     "ledger", "reorder/removal/duplicate detection"),
    ("model_skip_confidence_bound", "model/__init__.py",
     "if not (0.0 <= float(self.confidence) <= 1.0):",
     "if False:",
     "validation", "confidence [0,1] bound"),
    ("model_skip_valid_interval", "model/__init__.py",
     "if vf is not None and vt is not None and vt < vf:",
     "if False:",
     "temporal", "valid_to >= valid_from"),
    ("identity_skip_name_regex", "identity/__init__.py",
     "if not _NAME_RE.match(value):",
     "if False:",
     "identity", "namespace/tenant identifier validation (unicode confusables)"),
    ("identity_skip_owner_guard", "identity/__init__.py",
     'if owner_agent != self.agent and "admin" not in self.capabilities:',
     "if False:",
     "agent-isolation", "cross-agent write (owner) guard"),
    ("core_skip_ref_scope", "core/__init__.py",
     'obj.get("tenant") != principal.tenant or obj.get("namespace") != principal.namespace',
     "False",
     "tenant-isolation", "cross-tenant reference scope check"),
    ("core_supersede_no_close", "core/__init__.py",
     'obj["tx_to"] = p["tx_to"]',
     'obj["tx_to"] = None',
     "supersession", "supersede must close old belief"),
    ("core_import_no_verify", "core/__init__.py",
     "dict[str, Any], *, verify: bool = True, migrate: bool = False",
     "dict[str, Any], *, verify: bool = False, migrate: bool = False",
     "import", "import chain verification on tamper"),
    # --- EPISTEMOS-02 index-boundary mutants (ETAPA 19) ---
    ("idx_search_tenant_leak", "index/fts.py",
     "AND tenant = ? AND namespace = ?",
     "AND tenant != ? AND namespace = ?",
     "index-tenant", "FTS query tenant filter (cross-tenant leak)"),
    ("idx_temporal_and_to_or", "retrieval/__init__.py",
     "believed_at(obj, at_tx) and valid_at(obj, at_valid)",
     "believed_at(obj, at_tx) or valid_at(obj, at_valid)",
     "index-temporal", "temporal component = believed AND valid"),
    ("idx_persist_skip_reindex", "core/__init__.py",
     "self.lexical_index.reindex(obj)",
     "None",
     "index-consistency", "writes must update the index"),
    ("idx_verify_always_true", "index/fts.py",
     "ok = (set(mapping) == set(searchable)) and (map_count == idx_count)",
     "ok = True",
     "index-consistency", "verify detects index drift/corruption"),
    ("idx_fallback_inverted", "core/__init__.py",
     "self.lexical_index.health() == IndexHealth.HEALTHY",
     "self.lexical_index.health() != IndexHealth.HEALTHY",
     "index-fallback", "use index only when HEALTHY else fall back"),
    ("idx_lexical_zeroed", "retrieval/__init__.py",
     'comp["lexical"] = lexical',
     'comp["lexical"] = 0.0',
     "index-scoring", "lexical score contribution to explainability"),
    # --- EPISTEMOS-03 audit fixes: each mutant reopens a closed vulnerability ---
    ("core_import_scope_authority", "core/__init__.py",
     'if obj.get("tenant") != record.tenant or obj.get("namespace") != record.namespace:',
     "if False:",
     "tenant-isolation", "ledger header is the sole scope authority on import (A-01)"),
    ("core_belief_reclose", "core/__init__.py",
     'if obj.get("tx_to") is None:',
     "if True:",
     "bitemporal", "projection keeps the earliest belief close (A-12)"),
    ("core_open_belief_guard", "core/__init__.py",
     'if old.get("tx_to") is not None:',
     "if False:",
     "bitemporal", "refuse to re-close an already-closed belief (A-12)"),
    ("core_confirm_negative_delta", "core/__init__.py",
     "if delta < 0.0:",
     "if False:",
     "agent-isolation", "confirm only corroborates, never lowers confidence (B-03)"),
    ("retrieval_source_scope", "retrieval/__init__.py",
     'if src.get("tenant") != obj.get("tenant") or src.get("namespace") != obj.get("namespace"):',
     "if False:",
     "tenant-isolation", "source is never dereferenced across scope (B-06)"),
    ("idx_verify_content_drift", "index/fts.py",
     "if content.get(rid) != searchable.get(obj_id):",
     "if False:",
     "index-consistency", "verify detects FTS content-cell corruption (B-01)"),
    ("rest_none_principal", "api/rest.py",
     "if not isinstance(principal, Principal):",
     "if False:",
     "auth-fail-closed", "REST refuses a non-Principal from the auth resolver (B-01)"),
    # --- EPISTEMOS-04 Knowledge Spaces boundaries: each mutant reopens a leak ---
    ("spaces_private_default_to_public", "spaces/__init__.py",
     "    if value is None:\n        return Visibility.PRIVATE",
     "    if value is None:\n        return Visibility.PUBLIC",
     "spaces-fail-closed", "absent visibility defaults PRIVATE, never PUBLIC (§5)"),
    ("spaces_deny_to_allow", "authz/__init__.py",
     "    if obj.get(\"tenant\") != principal.tenant:\n        return False",
     "    if obj.get(\"tenant\") != principal.tenant:\n        return True",
     "space-tenant", "read decision fails closed on tenant mismatch"),
    ("spaces_owner_check_removed", "authz/__init__.py",
     "return bool(\n            obj.get(\"owner\") == principal.agent",
     "return bool(\n            True or obj.get(\"owner\") == principal.agent",
     "space-private", "a private object is readable only by its owner"),
    ("spaces_member_check_removed", "authz/__init__.py",
     "if vis == Visibility.TEAM and (owner == principal.agent or is_member(sid, principal.agent)):",
     "if vis == Visibility.TEAM:",
     "space-membership", "TEAM access requires ownership or a granted membership"),
    ("spaces_promote_cap_removed", "core/__init__.py",
     # noqa: this literal must match the source byte-for-byte to locate the mutation site.
     # Reflowing it would silently stop the mutant from applying — a survivor that never ran.
     'if dest_vis >= Visibility.ORGANIZATION and "admin" not in principal.capabilities:\n            principal.require("knowledge.promote")',  # noqa: E501
     'if False:\n            principal.require("knowledge.promote")',
     "space-promote", "promotion to ORG+ requires the knowledge.promote capability (§11)"),
    ("spaces_search_authorize_removed", "retrieval/__init__.py",
     "if authorize is not None and not authorize(obj):",
     "if False and authorize is not None and not authorize(obj):",
     "space-retrieval", "unauthorized candidates dropped before scoring (§12)"),
    ("spaces_grant_active_ignored", "core/__init__.py",
     'return grant is not None and grant.get("kind") == "grant" and bool(grant.get("active"))',
     'return grant is not None and grant.get("kind") == "grant"',
     "space-revocation", "a revoked (inactive) grant denies access (§22)"),
    # --- EPISTEMOS-05 Collaborative Claims boundaries: each mutant reopens a real hole ---
    ("claim_self_acceptance_removed", "core/__init__.py",
     'if (claim.get("claimant") == principal.agent',
     'if (False and claim.get("claimant") == principal.agent',
     "claim-governance", "a claimant cannot govern their own claim into truth (§32)"),
    ("claim_accept_cap_removed", "core/__init__.py",
     'principal.require("knowledge.accept")',
     'principal.require("claim.read")',
     "claim-truth-gate", "acceptance requires the non-default knowledge.accept capability"),
    ("claim_evidence_readability_removed", "core/__init__.py",
     "if ev is not None and self._can_read(principal, ev):",
     "if ev is not None:",
     "visibility-composition", "a public claim never exposes private evidence (§15)"),
    ("claim_ref_readable_oracle", "core/__init__.py",
     # noqa: exact-match mutation site (see the note above) — must not be reflowed.
     'if not self._can_read(principal, obj):\n            raise NotFoundError(f"{what} {ref_id!r} not found")',  # noqa: E501
     'if False:\n            raise NotFoundError(f"{what} {ref_id!r} not found")',
     "claim-firewall", "a claim outside the caller's spaces is invisible (no oracle §17)"),
    ("claim_review_space_inherit_removed", "core/__init__.py",
     'spaces=tuple(claim.get("spaces", ()))),',
     "spaces=()),",
     "review-leak", "a review inherits the claim's audience (REVIEW_SPACE_LEAK=0)"),
    ("belief_dispute_ignored", "claims/belief.py",
     "    if contested:",
     "    if False:",
     "belief-derivation", "one live dispute makes belief DISPUTED — majority is not truth (§9)"),
    ("belief_governance_hides_dispute", "claims/belief.py",
     'return f"; NOTE: {len(contested)} dispute/reject still on record" if contested else ""',
     'return ""',
     "belief-audit", "governed acceptance still records a coexisting dispute (§10)"),
]


def run_suite(pkg_parent: Path) -> int:
    import os

    env = {**os.environ, "PYTHONPATH": str(pkg_parent)}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TEST_TARGETS, *IGNORE, "-q", "-x", "--no-header", "-p",
         "no:cacheprovider"],
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
    # control: unmutated copy must pass the invariant suite
    with tempfile.TemporaryDirectory() as d:
        parent = Path(d)
        shutil.copytree(SRC, parent / "epistemos")
        control_rc = run_suite(parent)
    if control_rc != 0:
        print(f"CONTROL FAILED (rc={control_rc}) — harness setup is wrong; aborting")
        return 3

    results = []
    for mut_id, rel, find, replace, boundary, note in MUTANTS:
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            dest = parent / "epistemos"
            shutil.copytree(SRC, dest)
            if not apply_mutant(find, replace, rel, dest):
                results.append((mut_id, boundary, "INVALID", "snippet not found", note))
                continue
            rc = run_suite(parent)
        status = {0: "SURVIVED", 1: "KILLED"}.get(rc, "INVALID")
        results.append((mut_id, boundary, status, f"pytest rc={rc}", note))
        print(f"  {status:9} {mut_id:32} ({boundary}) — {note}")

    total = len(results)
    killed = sum(1 for r in results if r[2] == "KILLED")
    survived = sum(1 for r in results if r[2] == "SURVIVED")
    invalid = sum(1 for r in results if r[2] == "INVALID")

    report = _render(control_rc, results, total, killed, survived, invalid)
    out = REPO / "docs" / "security" / "MUTATION_REPORT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(f"\nTOTAL={total} KILLED={killed} SURVIVED={survived} INVALID={invalid}")
    print(f"wrote {out}")
    # every listed mutant is non-equivalent by construction; any survivor is a real gap
    return 0 if survived == 0 and invalid == 0 else 1


def _render(control_rc, results, total, killed, survived, invalid) -> str:
    lines = ["# EPISTEMOS Mutation Report (targeted critical-boundary harness)", ""]
    lines.append("Method: per-mutant, copy the package, apply one source mutation, "
                 "run the invariant")
    lines.append("suite against the copy, classify by pytest **exit code** "
                 "(mission §32). Reproduce:")
    lines.append("`python tools/mutation_harness.py`.")
    lines.append("")
    lines.append(f"- CONTROL (unmutated copy) pytest rc = {control_rc} (0 = green baseline)")
    lines.append("- Every mutant below is **non-equivalent by construction** (it changes a load-")
    lines.append("  bearing predicate), so the target is `SURVIVED == 0`.")
    lines.append("")
    lines.append("```")
    lines.append(f"MUTANTS_TOTAL              = {total}")
    lines.append(f"MUTANTS_NON_EQUIVALENT     = {total}   (all curated mutants change behavior)")
    lines.append(f"MUTANTS_KILLED            = {killed}")
    lines.append(f"MUTANTS_SURVIVED          = {survived}")
    lines.append(f"INVALID_MUTATIONS         = {invalid}")
    lines.append(f"CRITICAL_NON_EQUIVALENT_SURVIVED = {survived}")
    lines.append("```")
    lines.append("")
    lines.append("| mutant | boundary | result | detail | protects |")
    lines.append("|--------|----------|--------|--------|----------|")
    for mut_id, boundary, status, detail, note in results:
        lines.append(f"| `{mut_id}` | {boundary} | **{status}** | {detail} | {note} |")
    lines.append("")
    verdict = "PASS" if survived == 0 and invalid == 0 else "FAIL"
    lines.append(f"**MUTATION_CRITICAL = {verdict}**")
    lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
