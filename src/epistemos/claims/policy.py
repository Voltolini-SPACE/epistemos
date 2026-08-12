"""Policy port for governed acceptance (mission §18-19).

Accepting a claim as knowledge is a **governed** operation, not a click. EPISTEMOS enforces the
mechanics (identity, capability, space, provenance, ledgering) and delegates the *decision* to a
pluggable policy. The default is a local, deterministic policy so the engine works **standalone** —
NOMOS or another PDP can be wired later without the core depending on it.

A policy receives a :class:`PolicyRequest` and returns a :class:`PolicyDecision`. It never sees a
network; it is a pure decision over the material the engine already authorized the caller to see.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = ["PolicyRequest", "PolicyDecision", "Policy", "LocalDefaultPolicy"]


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    action: str  # "accept" | "reject"
    principal_agent: str
    principal_caps: frozenset[str]
    claim: dict[str, Any]
    reviews: list[dict[str, Any]]
    destination_space: str | None  # where the accepted knowledge would live


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allow: bool
    reason: str


Policy = Callable[[PolicyRequest], PolicyDecision]


class LocalDefaultPolicy:
    """The zero-config default: deterministic, no network, no LLM.

    Rules (deliberately conservative):

    * the principal must hold the ``knowledge.accept`` capability (fail closed);
    * a retracted or superseded claim cannot be accepted;
    * acceptance does not require a vote threshold — governance is explicit, not majority-rule
      (§9) — but the decision reason records the review picture for the audit trail.

    A deployment that wants "N independent confirmations required" plugs its own policy in; the
    core does not hard-code a social threshold.
    """

    def __call__(self, req: PolicyRequest) -> PolicyDecision:
        if "knowledge.accept" not in req.principal_caps:
            return PolicyDecision(False, "principal lacks the knowledge.accept capability")
        status = req.claim.get("status")
        if status in ("retracted", "superseded"):
            return PolicyDecision(False, f"cannot accept a {status} claim")
        confirms = sum(1 for r in req.reviews if r.get("verdict") == "confirm")
        disputes = sum(1 for r in req.reviews if r.get("verdict") in ("dispute", "reject"))
        if req.action == "reject":
            return PolicyDecision(True, f"rejected by policy (confirms={confirms}, disputes={disputes})")
        return PolicyDecision(True, f"accepted by policy (confirms={confirms}, disputes={disputes})")
