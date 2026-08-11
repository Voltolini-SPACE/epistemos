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

from datetime import datetime
from typing import Any

from .._util import now_utc, parse_instant

__all__ = [
    "instant_in_interval",
    "valid_at",
    "believed_at",
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
        if believed_only and not believed_at(f, at_tx):
            continue
        if at_valid is not None and not valid_at(f, at_valid):
            continue
        out.append(f)
    return out


def _rank_key(fact: dict[str, Any]) -> tuple[float, str, str]:
    """Higher is "more current": greater confidence, then later assertion time."""
    return (
        float(fact.get("confidence", 1.0)),
        str(fact.get("tx_from") or ""),
        str(fact.get("id") or ""),
    )


def resolve_current(
    facts: list[dict[str, Any]],
    *,
    at_valid: str | datetime | None = None,
    at_tx: str | datetime | None = None,
) -> dict[str, Any] | None:
    """Pick the single most-current fact from a same-(subject,predicate) group.

    A fact with ``object == None`` represents "the relation ended / has no value"; if the
    winning fact has a null object, there is no current value and ``None`` is returned.
    """
    candidates = as_of(facts, at_tx=at_tx, at_valid=at_valid, believed_only=True)
    if not candidates:
        return None
    best = max(candidates, key=_rank_key)
    if best.get("object") is None:
        return None
    return best
