"""Provenance genealogy (mission §11).

Provenance is first-class: every relevant object can answer *WHERE DID THIS COME FROM?*
The model is a lightweight mapping onto W3C PROV's three roles (see ADR-004):

* **Entity** (PROV) ── an EPISTEMOS object (fact, source, document, decision).
* **Activity** (PROV) ── a ledger event (`fact_asserted`, `document_ingested`, ...).
* **Agent** (PROV) ── the ``actor`` (agent) / ``principal`` on each ledger event.

``explain(obj_id)`` walks the derivation edges (``source``, ``derived_from``,
``supersedes``, ``contradicts``) and cross-references the tamper-evident ledger to list
the activities that touched the object — so the genealogy is auditable, not asserted.
"""

from __future__ import annotations

from typing import Any

from ..storage import Store

__all__ = ["explain", "explain_decision"]


def _refs_id(value: Any, obj_id: str) -> bool:
    """True if ``obj_id`` appears as a string leaf anywhere in ``value``. Short-circuits.

    Cheaper and more precise than serializing the whole payload: it compares actual string
    values (so a stray substring inside unrelated text cannot cause a false positive) and
    stops at the first match.
    """
    if isinstance(value, str):
        return value == obj_id
    if isinstance(value, dict):
        return any(_refs_id(v, obj_id) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_refs_id(v, obj_id) for v in value)
    return False


def _activities_for(store: Store, tenant: str, namespace: str, obj_id: str) -> list[dict[str, Any]]:
    """Ledger events (PROV activities) whose payload references ``obj_id``."""
    acts = []
    for rec in store.read_events():
        if rec.tenant != tenant or rec.namespace != namespace:
            continue
        if _refs_id(rec.payload, obj_id):
            acts.append(
                {
                    "seq": rec.seq,
                    "op": rec.op,
                    "ts": rec.ts,
                    "actor": rec.actor,
                    "principal": rec.principal,
                    "entry_hash": rec.entry_hash,
                }
            )
    return acts


def _source_view(store: Store, source_id: str | None) -> dict[str, Any] | None:
    if not source_id:
        return None
    src = store.get_object(source_id)
    if src is None:
        return {"id": source_id, "status": "missing"}
    return {
        "id": src["id"],
        "uri": src.get("uri"),
        "source_kind": src.get("source_kind"),
        "trust": src.get("trust"),
    }


def explain(
    store: Store,
    tenant: str,
    namespace: str,
    obj_id: str,
    *,
    depth: int = 3,
    _seen: set[str] | None = None,
) -> dict[str, Any]:
    """Produce the genealogy of an object as a bounded, cycle-safe tree.

    Scope is enforced by the caller (engine); this function only reads within
    ``(tenant, namespace)``.
    """
    seen = _seen if _seen is not None else set()
    obj = store.get_object(obj_id)
    if obj is None:
        return {"id": obj_id, "status": "missing"}
    if obj.get("tenant") != tenant or obj.get("namespace") != namespace:
        # Never cross a scope boundary while walking provenance.
        return {"id": obj_id, "status": "out_of_scope"}
    if obj_id in seen or depth < 0:
        return {"id": obj_id, "kind": obj.get("kind"), "status": "elided_cycle_or_depth"}
    seen.add(obj_id)

    node: dict[str, Any] = {
        "id": obj_id,
        "kind": obj.get("kind"),
        "confidence": obj.get("confidence"),
        "owner": obj.get("owner"),
        "created_at": obj.get("created_at"),
    }
    if obj.get("kind") == "fact":
        node["statement"] = {
            "subject": obj.get("subject"),
            "predicate": obj.get("predicate"),
            "object": obj.get("object"),
        }
        node["temporal_state"] = {
            "valid_from": obj.get("valid_from"),
            "valid_to": obj.get("valid_to"),
            "tx_from": obj.get("tx_from"),
            "tx_to": obj.get("tx_to"),
            "status": obj.get("status"),
            "believed": obj.get("tx_to") is None,
        }

    node["source"] = _source_view(store, obj.get("source"))
    node["activities"] = _activities_for(store, tenant, namespace, obj_id)

    def _walk(ids: list[str]) -> list[dict[str, Any]]:
        return [
            explain(store, tenant, namespace, ref, depth=depth - 1, _seen=seen) for ref in ids
        ]

    node["derived_from"] = _walk(list(obj.get("derived_from", [])))
    node["supersedes"] = _walk(list(obj.get("supersedes", [])))
    if obj.get("contradicts"):
        node["contradicts"] = list(obj.get("contradicts", []))

    # reverse edge: what supersedes THIS object
    superseded_by = [
        f["id"]
        for f in store.objects(tenant, namespace, kind="fact")
        if obj_id in f.get("supersedes", [])
    ]
    if superseded_by:
        node["superseded_by"] = superseded_by
    return node


def explain_decision(
    store: Store, tenant: str, namespace: str, decision_id: str
) -> dict[str, Any]:
    """Evidence and dependencies behind a decision (mission §11: WHAT EVIDENCE LED TO THIS?)."""
    dec = store.get_object(decision_id)
    if dec is None or dec.get("kind") != "decision":
        return {"id": decision_id, "status": "missing"}
    if dec.get("tenant") != tenant or dec.get("namespace") != namespace:
        return {"id": decision_id, "status": "out_of_scope"}
    evidence = [
        explain(store, tenant, namespace, ev_id, depth=2) for ev_id in dec.get("evidence", [])
    ]
    return {
        "id": decision_id,
        "statement": dec.get("statement"),
        "outcome": dec.get("outcome"),
        "reversible": dec.get("reversible"),
        "alternatives": list(dec.get("alternatives", [])),
        "evidence": evidence,
        "activities": _activities_for(store, tenant, namespace, decision_id),
    }
