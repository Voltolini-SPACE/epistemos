"""EPISTEMOS-03 audit: transaction time is append-only — a belief closes exactly once.

Finding A-12 (CRITICAL).

`supersede`, `correct_validity` and `retract` all close a belief by writing `tx_to`. None of
them checked whether the belief was *already* closed, so calling any of them twice on the same
fact overwrote the original `tx_to`. Measured on v0.2.0 with a 1-day clock:

    supersede(f1) -> f1.tx_to = 2026-01-03
    as_of(at_tx="2026-01-05") -> "Beta"
    supersede(f1) again -> f1.tx_to = 2026-01-04
    as_of(at_tx="2026-01-05") -> "Gamma"      # the past changed

The hash chain still verifies and `rebuild_projection()` faithfully reproduces the rewritten
state, so this is not corruption — it is the domain answering "what did the system believe at
T?" differently depending on what happened *after* T. That is precisely the property
bitemporality exists to prevent.

Two independent defences are tested here:

1. the command layer refuses to close an already-closed belief (fail closed);
2. the projection keeps the EARLIEST close, so even a ledger that already contains a double
   close — written before this fix, or hand-crafted — cannot move transaction time forward.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from epistemos import Engine, Principal
from epistemos.errors import ConflictError


class DayClock:
    """One day per call, so transaction-time boundaries are unambiguous."""

    def __init__(self) -> None:
        self.t = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        v = self.t
        self.t += timedelta(days=1)
        return v


@pytest.fixture
def eng(store, ctx: Principal) -> Engine:
    return Engine(store, clock=DayClock())


def _setup(eng: Engine, ctx: Principal):
    src = eng.add_source(ctx, uri="mem://s", trust=0.5)
    f1 = eng.assert_fact(ctx, subject="Alice", predicate="works_at",
                         object="Acme", source=src.id)
    return src, f1


def test_supersede_refuses_already_closed_belief(eng: Engine, ctx: Principal) -> None:
    _, f1 = _setup(eng, ctx)
    eng.supersede(ctx, f1.id, new=dict(object="Beta"))
    closed_at = eng.store.get_object(f1.id)["tx_to"]
    with pytest.raises(ConflictError, match="already closed"):
        eng.supersede(ctx, f1.id, new=dict(object="Gamma"))
    assert eng.store.get_object(f1.id)["tx_to"] == closed_at


def test_retract_refuses_already_closed_belief(eng: Engine, ctx: Principal) -> None:
    _, f1 = _setup(eng, ctx)
    eng.supersede(ctx, f1.id, new=dict(object="Beta"))
    closed_at = eng.store.get_object(f1.id)["tx_to"]
    status = eng.store.get_object(f1.id)["status"]
    with pytest.raises(ConflictError, match="already closed"):
        eng.retract(ctx, f1.id, reason="too late")
    obj = eng.store.get_object(f1.id)
    assert obj["tx_to"] == closed_at and obj["status"] == status


def test_correct_validity_refuses_already_closed_belief(eng: Engine, ctx: Principal) -> None:
    _, f1 = _setup(eng, ctx)
    eng.retract(ctx, f1.id, reason="withdrawn")
    closed_at = eng.store.get_object(f1.id)["tx_to"]
    with pytest.raises(ConflictError, match="already closed"):
        eng.correct_validity(ctx, f1.id, valid_to="2026-05-01")
    assert eng.store.get_object(f1.id)["tx_to"] == closed_at


def test_the_past_does_not_change(eng: Engine, ctx: Principal) -> None:
    """The property the whole gate exists for."""
    _, f1 = _setup(eng, ctx)
    eng.supersede(ctx, f1.id, new=dict(object="Beta"))
    probe = "2026-01-05T00:00:00Z"
    before = eng.as_of(ctx, "2027-01-01", subject="Alice", predicate="works_at", at_tx=probe)
    with pytest.raises(ConflictError):
        eng.supersede(ctx, f1.id, new=dict(object="Gamma"))
    after = eng.as_of(ctx, "2027-01-01", subject="Alice", predicate="works_at", at_tx=probe)
    assert before == after == "Beta"


def test_superseding_the_current_generation_still_chains(eng: Engine, ctx: Principal) -> None:
    """Anti-regression: A -> B -> C works; you supersede the *believed* fact, not a closed one."""
    _, f1 = _setup(eng, ctx)
    f2 = eng.supersede(ctx, f1.id, new=dict(object="Beta"))
    f3 = eng.supersede(ctx, f2.id, new=dict(object="Gamma"))
    assert eng.store.get_object(f1.id)["tx_to"] is not None
    assert eng.store.get_object(f2.id)["tx_to"] is not None
    assert eng.store.get_object(f3.id)["tx_to"] is None
    assert eng.as_of(ctx, "2027-01-01", subject="Alice", predicate="works_at") == "Gamma"
    # each generation's transaction interval is distinct and ordered
    txs = [eng.store.get_object(f.id)["tx_from"] for f in (f1, f2, f3)]
    assert txs == sorted(txs) and len(set(txs)) == 3


def test_projection_keeps_the_earliest_close(eng: Engine, ctx: Principal) -> None:
    """Defence 2: a ledger that already contains a double close cannot move tx_to forward.

    Replays a hand-built double-close directly through the projection, which is what a legacy
    database or a crafted import looks like on rebuild.
    """
    from epistemos.ledger import Event, Op
    from epistemos.model import BeliefStatus

    _, f1 = _setup(eng, ctx)
    eng.supersede(ctx, f1.id, new=dict(object="Beta"))
    first_close = eng.store.get_object(f1.id)["tx_to"]

    later = "2099-01-01T00:00:00Z"
    with eng.store.atomic():
        rec = eng.store.append(Event(
            op=Op.FACT_RETRACTED, ts=later, tenant=ctx.tenant, namespace=ctx.namespace,
            actor=ctx.agent, principal=None,
            payload={"fact_id": f1.id, "tx_to": later,
                     "status": BeliefStatus.RETRACTED.value, "reason": "replayed"},
        ))
        eng._apply(rec)
    assert eng.store.get_object(f1.id)["tx_to"] == first_close

    eng.rebuild_projection()
    assert eng.store.get_object(f1.id)["tx_to"] == first_close
