"""Authorized event stream (ADR-031/032, mission §34).

The panel's realtime feed is a **tail of the ledger**, filtered **at the source**. For each new
ledger record we (1) drop it unless it is in the caller's tenant *and* namespace (cheapest,
absolute), (2) resolve the object the event concerns, (3) emit **only** if ``Engine.is_readable``
passes, and (4) emit a **redacted envelope** — never the raw payload. A private claim's assertion,
an evidence attachment on a claim you cannot see, a review in a space you are not in: none of these
ever reach the browser. There is no client-side filtering — the browser cannot filter what it never
receives.

``authorized_events`` is the single primitive behind both the SSE stream and the Activity feed, so
there is one code path to secure and to test (``PRIVATE_STREAM_LEAK = 0``).
"""

from __future__ import annotations

from typing import Any

from ..core import Engine
from ..identity import Principal, require_principal
from .panel import _label, concerned_object_id

__all__ = ["authorized_events", "event_kind_for"]

# ledger op -> panel event kind (the vocabulary the UI subscribes to)
_OP_KIND = {
    "claim_asserted": "claim.created",
    "claim_retracted": "claim.retracted",
    "claim_superseded": "claim.superseded",
    "evidence_recorded": "evidence.created",
    "evidence_attached": "evidence.attached",
    "claim_reviewed": "review.created",
    "claim_accepted": "knowledge.accepted",
    "claim_rejected": "knowledge.rejected",
    "fact_asserted": "fact.asserted",
    "fact_superseded": "fact.superseded",
    "fact_retracted": "fact.retracted",
    "fact_confirmed": "fact.confirmed",
    "contradiction_recorded": "contradiction.recorded",
    "relation_added": "relation.created",
    "entity_added": "entity.created",
    "decision_recorded": "decision.created",
    "source_added": "source.added",
    "observation_recorded": "observation.recorded",
    "document_ingested": "document.ingested",
}


def event_kind_for(op: str) -> str:
    return _OP_KIND.get(op, op)


def authorized_events(
    engine: Engine, principal: Principal, *, since_seq: int = 0, max_events: int = 500
) -> list[dict[str, Any]]:
    """Redacted, authorized event envelopes for records with ``seq > since_seq``.

    Each envelope is ``{seq, op, kind, ts, actor, object, object_kind, summary}``. Only events
    whose concerned object the ``principal`` may read are kept; the rest are dropped server-side.
    """
    principal = require_principal(principal)
    out: list[dict[str, Any]] = []
    store = engine.store
    for rec in store.read_events(since_seq=since_seq):
        # (1) cross-tenant / cross-namespace: absolute, cheapest drop
        if rec.tenant != principal.tenant or rec.namespace != principal.namespace:
            continue
        payload = dict(rec.payload) if isinstance(rec.payload, dict) else {}
        obj_id = concerned_object_id(rec.op, payload)
        if obj_id is None:
            continue
        # (2)+(3) resolve the CURRENT projected object and authorize by readability
        obj = store.get_object(obj_id)
        if obj is None or not engine.is_readable(principal, obj):
            continue  # private / absent — never surfaces
        # (4) redacted envelope only — the raw payload never leaves the server
        out.append({
            "seq": rec.seq,
            "op": rec.op,
            "kind": event_kind_for(rec.op),
            "ts": rec.ts,
            "actor": rec.actor,
            "object": obj_id,
            "object_kind": obj.get("kind"),
            "summary": _summary(rec.op, obj),
        })
        if len(out) >= max_events:
            break
    return out


def _summary(op: str, obj: dict[str, Any]) -> str:
    """A one-line, safe human summary built from a READABLE object's own label (no private ref)."""
    label = _label(obj)
    verb = {
        "claim_asserted": "claimed",
        "claim_retracted": "retracted claim",
        "claim_superseded": "superseded claim",
        "evidence_recorded": "recorded evidence",
        "evidence_attached": "attached evidence to",
        "claim_reviewed": "reviewed",
        "claim_accepted": "accepted",
        "claim_rejected": "rejected",
        "fact_asserted": "asserted",
        "fact_confirmed": "confirmed",
        "contradiction_recorded": "recorded contradiction on",
        "relation_added": "linked",
        "entity_added": "added entity",
        "decision_recorded": "decided",
        "source_added": "added source",
    }.get(op, op.replace("_", " "))
    return f"{verb} {label}".strip()
