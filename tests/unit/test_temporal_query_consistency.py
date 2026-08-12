"""EPISTEMOS-03 audit: temporal queries must use one coherent time axis.

Findings T-05 (current() mixes the injected clock and wall-clock) and T-06 (believed_only
ignores at_tx). Both make a temporal query answer inconsistently with the clock the engine was
given — which matters for deterministic replay and for "as of" reconstruction.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from epistemos import Engine, Principal
from epistemos.storage import MemoryStore

CTX = Principal(tenant="acme", agent="a", namespace="hr")


class Clock:
    def __init__(self, start: datetime) -> None:
        self.t = start

    def __call__(self) -> datetime:
        v = self.t
        self.t += timedelta(seconds=1)
        return v


def test_current_uses_engine_clock_not_wall_clock() -> None:
    """T-05: with a clock far from wall time, current() must still see a just-asserted fact."""
    for start in (datetime(2099, 1, 1, tzinfo=UTC), datetime(2000, 1, 1, tzinfo=UTC)):
        eng = Engine(MemoryStore(), clock=Clock(start))
        s = eng.add_source(CTX, uri="mem://s", trust=0.9)
        eng.assert_fact(CTX, subject="X", predicate="p", object="V", source=s.id)
        assert eng.current(CTX, subject="X", predicate="p") == "V", \
            f"current() disagreed with the engine clock at {start}"


def test_believed_only_respects_at_tx() -> None:
    """T-06: search(at_tx=T, believed_only=True) means 'believed at T', not 'believed now'."""
    eng = Engine(MemoryStore(), clock=Clock(datetime(2026, 1, 1, tzinfo=UTC)))
    s = eng.add_source(CTX, uri="mem://s", trust=0.9)
    f = eng.assert_fact(CTX, subject="Y", predicate="p", object="oldvalue", source=s.id)
    at_when_old_believed = eng.store.get_object(f.id)["tx_from"]
    eng.supersede(CTX, f.id, new=dict(object="newvalue"))

    # believed NOW: the old fact is no longer believed
    now_hits = {r["id"] for r in eng.search(CTX, text="oldvalue", believed_only=True, limit=10)}
    assert f.id not in now_hits

    # believed AT the tx instant when it WAS believed: it must be returned
    past_hits = {
        r["id"]
        for r in eng.search(CTX, text="oldvalue", believed_only=True,
                            at_tx=at_when_old_believed, limit=10)
    }
    assert f.id in past_hits, "believed_only ignored at_tx and filtered on 'believed now'"


def test_believed_only_default_is_now() -> None:
    """Anti-regression: without at_tx, believed_only still means 'believed now'."""
    eng = Engine(MemoryStore(), clock=Clock(datetime(2026, 1, 1, tzinfo=UTC)))
    s = eng.add_source(CTX, uri="mem://s", trust=0.9)
    f = eng.assert_fact(CTX, subject="Z", predicate="p", object="tok", source=s.id)
    eng.supersede(CTX, f.id, new=dict(object="tok2"))
    hits = {r["id"] for r in eng.search(CTX, text="tok", believed_only=True, limit=10)}
    assert f.id not in hits
