"""Belief derivation — belief is COMPUTED from reviews + governed acceptance, never a stored
boolean (mission §10). Every state is explainable (WHY_*). Majority is not truth (§9): acceptance
is a governed act, not a vote count; the derivation surfaces disputes rather than out-voting them.
"""

from __future__ import annotations

from typing import Any

from . import BeliefState, ClaimStatus, Verdict

__all__ = ["derive_belief"]


def derive_belief(
    claim: dict[str, Any],
    reviews: list[dict[str, Any]],
    *,
    accepted: dict[str, Any] | None = None,
    rejected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return ``{"state": BeliefState, "why": str, "reviews": [...], "governance": {...}}``.

    Precedence (highest first): the claim's own lifecycle (retracted/superseded) ⟶ a governed
    acceptance/rejection ⟶ the review picture (disputed ⟶ supported ⟶ proposed). Governance
    (accept/reject) is separate from and dominates individual reviews, but a governed acceptance
    does **not** erase a coexisting dispute — the ``why`` records both, so the audit trail is whole.
    """
    status = claim.get("status")
    if status == ClaimStatus.RETRACTED.value:
        return _r(BeliefState.RETRACTED, "the claim was retracted by its owner", reviews)
    if status == ClaimStatus.SUPERSEDED.value:
        return _r(BeliefState.SUPERSEDED, "the claim was superseded by a newer claim", reviews)

    confirms = [r for r in reviews if r.get("verdict") == Verdict.CONFIRM.value]
    disputes = [r for r in reviews if r.get("verdict") == Verdict.DISPUTE.value]
    rejects = [r for r in reviews if r.get("verdict") == Verdict.REJECT.value]
    contested = disputes + rejects

    if rejected is not None:
        why = (f"rejected under policy by {rejected.get('actor')!r}"
               f"{_and_disputes(contested)}")
        return _r(BeliefState.REJECTED, why, reviews, governance=rejected)
    if accepted is not None:
        why = (f"accepted under policy by {accepted.get('actor')!r} "
               f"({len(confirms)} confirm(s)){_and_disputes(contested)}")
        return _r(BeliefState.ACCEPTED, why, reviews, governance=accepted)

    if contested:
        why = (f"{len(contested)} live dispute/reject vs {len(confirms)} confirm — "
               "coexisting positions preserved; majority is not truth")
        return _r(BeliefState.DISPUTED, why, reviews)
    if confirms:
        return _r(BeliefState.SUPPORTED, f"{len(confirms)} confirmation(s), no live dispute", reviews)
    return _r(BeliefState.PROPOSED, "no review yet", reviews)


def _and_disputes(contested: list[dict[str, Any]]) -> str:
    return f"; NOTE: {len(contested)} dispute/reject still on record" if contested else ""


def _r(state: BeliefState, why: str, reviews: list[dict[str, Any]],
       governance: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "state": str(state),
        "why": why,
        "reviews": [
            {"reviewer": r.get("owner"), "verdict": r.get("verdict"),
             "rationale": r.get("rationale"), "at": r.get("created_at")}
            for r in reviews
        ],
        "governance": governance,
    }
