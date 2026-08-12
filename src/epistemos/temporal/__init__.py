"""Bitemporal semantics (mission §10).

Two independent axes, both half-open intervals ``[from, to)`` with ``None`` meaning
unbounded:

* **valid time** — ``valid_from``/``valid_to`` — when a statement is true *in the world*.
* **transaction time** — ``tx_from``/``tx_to`` — when the *system believed* it.

This module is pure (dict in, bool/list out) so both storage adapters and every query
path share exactly one definition of "current", "believed at T", and "valid at T". The
question the mission insists on — *WHAT DID THE SYSTEM KNOW AT TIME T?* — is answered by
combining :func:`believed_at` (transaction axis) with :func:`valid_at` (valid axis).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from .._util import now_utc, parse_instant

__all__ = [
    "instant_in_interval",
    "valid_at",
    "believed_at",
    "believed",
    "as_of",
    "resolve_current",
]


def instant_in_interval(
    instant: datetime, lo: str | datetime | None, hi: str | datetime | None
) -> bool:
    """``lo <= instant < hi`` with ``None`` bounds treated as -inf / +inf."""
    lo_dt = parse_instant(lo)
    hi_dt = parse_instant(hi)
    after_lo = lo_dt is None or instant >= lo_dt
    before_hi = hi_dt is None or instant < hi_dt
    return after_lo and before_hi


def valid_at(fact: dict[str, Any], instant: str | datetime | None = None) -> bool:
    """Is the fact's world-statement valid at ``instant`` (default: now)?"""
    when = parse_instant(instant) if instant is not None else now_utc()
    assert when is not None
    return instant_in_interval(when, fact.get("valid_from"), fact.get("valid_to"))


def believed_at(fact: dict[str, Any], instant: str | datetime | None = None) -> bool:
    """Did the system believe the fact at transaction-time ``instant`` (default: now)?"""
    when = parse_instant(instant) if instant is not None else now_utc()
    assert when is not None
    return instant_in_interval(when, fact.get("tx_from"), fact.get("tx_to"))


def believed(fact: dict[str, Any], at_tx: str | datetime | None) -> bool:
    """Belief predicate for queries: at an explicit ``at_tx`` use the belief interval; with
    ``at_tx is None`` ("now") use whether the interval is still OPEN (``tx_to is None``).

    The open-interval definition of "believed now" is clock-independent, so ``current`` and
    ``believed_only`` do not depend on how the engine's clock relates to the data's transaction
    timestamps (EPISTEMOS-03, T-05). Historical reconstruction (``at_tx=T``) still anchors on T.
    """
    if at_tx is None:
        return fact.get("tx_to") is None
    return believed_at(fact, at_tx)


def as_of(
    facts: list[dict[str, Any]],
    *,
    at_tx: str | datetime | None = None,
    at_valid: str | datetime | None = None,
    believed_only: bool = True,
) -> list[dict[str, Any]]:
    """Filter facts to those the system believed at ``at_tx`` and (optionally) that were
    valid at ``at_valid``. With both set you reconstruct a full point-in-time view.
    """
    out = []
    for f in facts:
        if believed_only and not believed(f, at_tx):
            continue
        if at_valid is not None and not valid_at(f, at_valid):
            continue
        out.append(f)
    return out


TrustOf = Callable[[dict[str, Any]], float]


def _rank_key(fact: dict[str, Any], trust_of: TrustOf | None) -> tuple[float, float, str, str]:
    """Precedence for "most current" among contradictory believed facts, in order:

    1. **source trust** (authority) — a trusted source outranks a rumour regardless of recency;
    2. **confidence** — the asserted confidence of the fact;
    3. **transaction time** — more recently asserted wins ties;
    4. id — final deterministic tiebreak.

    Trust and confidence stay *separate* dimensions (mission §15): they are distinct tuple
    components, never blended into one scalar.
    """
    return (
        float(trust_of(fact)) if trust_of is not None else 0.0,
        float(fact.get("confidence", 1.0)),
        str(fact.get("tx_from") or ""),
        str(fact.get("id") or ""),
    )


def resolve_current(
    facts: list[dict[str, Any]],
    *,
    at_valid: str | datetime | None = None,
    at_tx: str | datetime | None = None,
    trust_of: TrustOf | None = None,
) -> dict[str, Any] | None:
    """Pick the single most-current fact from a same-(subject,predicate) group.

    ``trust_of`` maps a fact to its backing source's trust (authority) and, when supplied,
    dominates the ranking so a low-trust contradiction cannot become "current". A fact with
    ``object == None`` means "the relation ended"; if the winner is null, there is no current
    value and ``None`` is returned.
    """
    candidates = as_of(facts, at_tx=at_tx, at_valid=at_valid, believed_only=True)
    if not candidates:
        return None
    best = max(candidates, key=lambda f: _rank_key(f, trust_of))
    if best.get("object") is None:
        return None
    return best
