"""EPCTX/1 wire document (mission §2, §3, §7-§12, §23, §24).

The **wire document** is the formal, sectioned interop form of a Context Envelope. A projection
over the internal :class:`~epistemos.context.builder.ContextEnvelope`: the core may evolve, but
this projection is the stable contract (an internal change does not break ``EPCTX/1`` while the
semantics hold, §3).

Design commitments the projection enforces:

* **Types are explicit** (§23, §24): every object carries ``object_type`` (fact/claim/evidence/
  review/decision/source), and claims carry ``belief_state`` + ``accepted_state`` so a consumer can
  never mistake a disputed *claim* for an accepted *fact*.
* **Contradictions are a section, not prose** (§8): disputing evidence is separated from supporting
  context, so ``THIS CONTEXT IS DISPUTED`` is a field, not something to infer from text.
* **Completeness is declared** (§7): ``completeness.complete`` + machine reasons; silence is never
  "nothing to know".
* **Temporal is a contract** (§9): each object exposes valid/transaction time and ``is_current``;
  the document says whether it carries current and/or historical state — no manual timestamp math.
* **Provenance is queryable** (§10): per-object source / derived_from / evidence refs answer "why is
  this here?" without knowing internals.
* **Tokens are accounted, honestly** (§11): ``token_estimate`` + ``tokens_by_section``, named an
  estimate, with the tokenizer profile recorded.
* **Integrity travels with it** (§6): ``integrity.context_hash`` over the canonical document.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..context.builder import ContextEnvelopeBuilder, EnvelopeConfig, estimate_tokens
from ..identity import Principal, require_principal
from .serialize import HASH_ALGO, context_hash
from .versioning import PROTOCOL_VERSION, assert_required

if TYPE_CHECKING:
    from ..core import Engine

__all__ = ["build_epctx", "project_object", "TOKENIZER_PROFILE"]

TOKENIZER_PROFILE = "chars-per-token-4/estimate-1"

_KIND_TO_TYPE = {
    "fact": "fact", "claim": "claim", "evidence": "evidence",
    "review": "review", "decision": "decision", "source": "source",
}
_SECTION_FOR = {
    "fact": "facts", "claim": "claims", "evidence": "evidence",
    "review": "reviews", "decision": "decisions", "source": "sources",
}


def _object_text(obj: dict[str, Any]) -> str:
    kind = obj.get("kind")
    if kind in ("fact", "claim"):
        parts = [str(obj.get("subject") or ""), str(obj.get("predicate") or ""),
                 str(obj.get("object") or "")]
        return " ".join(p for p in parts if p).strip()
    if kind == "evidence":
        return str(obj.get("title") or obj.get("uri") or "")
    if kind == "decision":
        return str(obj.get("statement") or "")
    if kind == "review":
        return str(obj.get("verdict") or obj.get("statement") or obj.get("note") or "")
    if kind == "source":
        return str(obj.get("uri") or "")
    return str(obj.get("id") or "")


def _is_current(obj: dict[str, Any]) -> bool:
    if obj.get("kind") == "fact":
        return obj.get("tx_to") is None
    if obj.get("kind") == "claim":
        return obj.get("status") in (None, "open", "accepted", "supported", "proposed")
    return True


def _belief(engine: Engine, principal: Principal, obj: dict[str, Any]) -> tuple[str | None, Any]:
    """Return ``(belief_state, accepted_state)``. A fact is ``asserted``; a claim's
    belief is DERIVED (never a stored boolean) and acceptance is governed; the two must never be
    conflated (§24)."""
    kind = obj.get("kind")
    if kind == "fact":
        return "asserted", None
    if kind == "claim":
        try:
            state = str(engine.belief(principal, obj["id"]).get("state") or "proposed")
        except Exception:  # noqa: BLE001 - belief unavailable -> fall back to a conservative marker
            state = str(obj.get("status") or "proposed")
        return state, state == "accepted"
    return None, None


def project_object(engine: Engine, principal: Principal, obj: dict[str, Any], *, role: str,
                   at_tx: str | None) -> dict[str, Any]:
    """Project one authorized object into its typed wire form. Assumes the object was already
    authorized by the caller (retrieval firewall or handle re-authorization)."""
    kind = str(obj.get("kind") or "")
    text = _object_text(obj)
    belief_state, accepted_state = _belief(engine, principal, obj)
    derived_from = [d for d in (obj.get("derived_from") or []) if isinstance(d, str)]
    evidence_refs = [e for e in (obj.get("evidence") or []) if isinstance(e, str)]
    source = obj.get("source") if isinstance(obj.get("source"), str) else None
    return {
        "id": obj.get("id"),
        "object_type": _KIND_TO_TYPE.get(kind, kind or "unknown"),
        "text": text,
        "role": role,
        "belief_state": belief_state,
        "accepted_state": accepted_state,
        "relation": (obj.get("metadata") or {}).get("relation") if kind == "evidence" else None,
        "temporal": {
            "valid_from": obj.get("valid_from"),
            "valid_to": obj.get("valid_to"),
            "transaction_from": obj.get("tx_from") or obj.get("created_at"),
            "transaction_to": obj.get("tx_to"),
            "is_current": _is_current(obj),
        },
        "provenance": {
            "source": source,
            "derived_from": derived_from,
            "evidence_refs": evidence_refs,
        },
        "tokens": estimate_tokens(text),
    }


def _config_for(requested_budget: int | None) -> EnvelopeConfig:
    if requested_budget is not None and requested_budget > 0:
        # Honor an explicit budget via the experimental packer (ADR-037), which never drops a pinned
        # contradiction or a critical item and declares any drop in completeness.
        return EnvelopeConfig(budget_pack=True, token_budget=requested_budget, continuation=True)
    return EnvelopeConfig()


def build_epctx(engine: Engine, principal: Principal, *, query: str | None,
                intent: str | None = None, as_of: str | None = None,
                requested_budget: int | None = None,
                consumer_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the EPCTX/1 wire document for an authorized principal. Identity is the caller's;
    here reads authority from ``consumer_profile`` or ``query`` (§17)."""
    principal = require_principal(principal)
    if consumer_profile is not None and not isinstance(consumer_profile, dict):
        raise TypeError("consumer_profile must be an object")
    budget = requested_budget
    if budget is None and consumer_profile:
        mct = consumer_profile.get("max_context_tokens")
        budget = int(mct) if isinstance(mct, int) and mct > 0 else None

    env = ContextEnvelopeBuilder(engine).build(
        principal, query, config=_config_for(budget), at_tx=as_of, intent=intent)

    from .handles import registry_for
    reg = registry_for(engine)

    contradiction_ids = set(env.pinned_contradictions)
    context: dict[str, list[dict[str, Any]]] = {
        "facts": [], "claims": [], "evidence": [], "reviews": [], "decisions": [], "sources": [],
    }
    contradictions: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    has_current = has_historical = False

    for item in env.items:
        obj = engine.store.get_object(item.object_id)
        if obj is None:
            continue
        proj = project_object(engine, principal, obj, role=item.role, at_tx=as_of)
        if proj["temporal"]["is_current"]:
            has_current = True
        else:
            has_historical = True
        provenance_rows.append({"id": proj["id"], "object_type": proj["object_type"],
                                **proj["provenance"]})
        if item.object_id in contradiction_ids:
            contradictions.append({"id": proj["id"], "object_type": proj["object_type"],
                                   "text": proj["text"], "relation": proj["relation"],
                                   "provenance": proj["provenance"]})
            continue
        section = _SECTION_FOR.get(str(obj.get("kind")))
        if section is not None:
            context[section].append(proj)

    expansion_handles = []
    for g in env.collapsed_groups:
        token = reg.mint(principal, member_ids=list(g.collapsed), at_tx=as_of, group_kind=g.kind)
        expansion_handles.append({"handle": token, "group_kind": g.kind,
                                  "collapsed_count": len(g.collapsed),
                                  "tokens_saved": g.tokens_saved})

    tokens_by_section = {name: sum(o["tokens"] for o in objs) for name, objs in context.items()}
    tokens_by_section["contradictions"] = sum(c and estimate_tokens(c["text"]) or 0
                                              for c in contradictions)

    document: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "request": {
            "query": query,
            "intent": env.intent,
            "intent_confidence": env.intent_confidence,
            "temporal_scope": {"as_of": as_of},
            "requested_budget": budget,
            "consumer_profile": consumer_profile,
        },
        "context": context,
        "contradictions": contradictions,
        "disputed": bool(contradictions),
        "temporal": {
            "as_of": as_of,
            "has_current_state": has_current,
            "has_historical_state": has_historical,
        },
        "completeness": {
            "complete": not env.context_incomplete,
            "reasons": list(env.incomplete_reasons),
        },
        "provenance": {"items": provenance_rows, "refs": list(env.provenance_refs)},
        "token_estimate": env.token_estimate,
        "tokens_by_section": tokens_by_section,
        "tokenizer_profile": TOKENIZER_PROFILE,
        "expansion": {"available": bool(expansion_handles), "handles": expansion_handles},
        "metadata": {},
    }
    document["integrity"] = {"algo": HASH_ALGO, "context_hash": context_hash(document)}
    assert_required(document)
    return document
