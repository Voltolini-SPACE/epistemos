"""The Context Envelope builder (EPISTEMOS v0.6).

A **post-retrieval** transform. Given the objects the current retrieval already returned
(authorized, unchanged), it produces a :class:`ContextEnvelope` (schema ``EPCTX/1``) that carries
the same knowledge in fewer tokens — provably without losing a critical piece of evidence, a
contradiction, or required history, and hiding nothing it left out.

What may be collapsed (safe redundancy):

* **superseded current-state versions** of one statement — but ONLY when the query is confidently
  about the *current* state; an uncertain or historical intent preserves the history inline;
* **true duplicates** — identical content (same ``content_hash``).

What is NEVER collapsed away:

* contradictions (they are pinned, including one attached to a retrieved claim);
* independent corroboration — the same finding from *different sources* keeps its provenance
  (``corroboration ≠ duplicate``): the repeated content is shown once, but every source is retained;
* historically-relevant versions, decisions, reviews, evidence with unique provenance.

Every collapse keeps each folded id and its provenance reachable, and any omission sets
``context_incomplete`` with a reason. Token-budget packing and continuation handles are experimental
(off by default) and can never remove a critical item or a contradiction.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from ..core import Engine
from ..identity import Principal, require_principal

_SKIP_KINDS = {"space", "grant", "dimension", "microconnection"}
_WORD_RE = re.compile(r"[a-z0-9]+")

# intent → whether history may be collapsed. Only a CONFIDENT current-state intent is safe; anything
# else (historical / change / decision / contradiction / uncertain) preserves history (§8 intent
# safety: token economy never beats recall).
_CURRENT_MARKERS = ("now", "current", "currently", "today", "latest", "present")
_HISTORY_MARKERS = ("before", "previous", "prior", "used to", "history", "historical", "was ",
                    "were ", "originally", "back then", "earlier")
_CHANGE_MARKERS = ("change", "changed", "what changed", "evolve", "evolved", "difference", "diff")
_WHY_MARKERS = ("why", "reason", "led to", "decide", "decision", "rationale")
_CONTRA_MARKERS = ("contradict", "conflict", "dispute", "disputed", "still true", "really",
                   "actually", "under control", "compliant")


def estimate_tokens(text: str) -> int:
    """~4 characters per token — a deterministic, reproducible estimate (stated as an estimate)."""
    return max(1, math.ceil(len(text) / 4))


def classify_intent(query: str | None) -> tuple[str, str]:
    """Return ``(intent, confidence)``. Confidence is ``"high"`` only when the query clearly signals
    a single intent; ambiguous or unmarked queries get ``"low"`` so collapse stays conservative."""
    q = f" {(query or '').lower()} "
    hits = {
        "historical": any(m in q for m in _HISTORY_MARKERS),
        "change": any(m in q for m in _CHANGE_MARKERS),
        "decision": any(m in q for m in _WHY_MARKERS),
        "contradiction": any(m in q for m in _CONTRA_MARKERS),
        "current": any(m in q for m in _CURRENT_MARKERS),
    }
    active = [k for k, v in hits.items() if v]
    # a query that mixes 'current' with a history/change signal is NOT a safe current-state query
    if hits["historical"] or hits["change"]:
        return ("change" if hits["change"] else "historical", "high")
    if hits["contradiction"]:
        return "contradiction", "high"
    if hits["decision"]:
        return "decision", "high"
    if hits["current"] and len(active) == 1:
        return "current", "high"
    # no decisive signal → treat as current but LOW confidence (do not collapse history)
    return "current", "low"


def _may_collapse_history(intent: str, confidence: str) -> bool:
    return intent == "current" and confidence == "high"


# ---- object helpers --------------------------------------------------------
def _label(o: dict[str, Any]) -> str:
    k = o.get("kind")
    if k in ("claim", "fact"):
        parts = (o.get("subject"), o.get("predicate"), o.get("object"))
        return " ".join(str(x) for x in parts if x)
    if k == "evidence":
        return str(o.get("title") or o.get("uri") or o.get("id"))
    if k == "decision":
        return str(o.get("statement") or o.get("id"))
    if k == "source":
        return str(o.get("uri") or o.get("id"))
    if k == "review":
        return f"{o.get('verdict', 'review')} of {str(o.get('claim_id', ''))[:10]}"
    return str(o.get("id"))


def _serialize(o: dict[str, Any]) -> str:
    k = o.get("kind", "object")
    extra = ""
    if k == "claim":
        extra = f" [status={o.get('status', 'open')}]"
    elif k == "evidence":
        rel = o.get("metadata", {}).get("relation")
        extra = f" [{rel}]" if rel else ""
    elif k == "fact":
        extra = " [current]" if o.get("tx_to") is None else " [superseded]"
    return f"{k}: {_label(o)}{extra}"


def _is_contradiction(o: dict[str, Any]) -> bool:
    return o.get("kind") == "evidence" and o.get("metadata", {}).get("relation") in (
        "contradicts", "weakens")


def _is_current(o: dict[str, Any]) -> bool:
    if o.get("kind") == "fact":
        return o.get("tx_to") is None
    if o.get("kind") == "claim":
        return o.get("status") in (None, "open", "accepted", "supported", "proposed")
    return True


def _statement_key(o: dict[str, Any]) -> str | None:
    k = o.get("kind")
    if k in ("fact", "claim"):
        return f"{k}:{o.get('subject')}|{o.get('predicate')}"
    return None


def _content_key(o: dict[str, Any]) -> str | None:
    """True-duplicate key for evidence: content hash only (identical content). Title/uri alone is
    NOT enough — same finding from different sources is corroboration, not a duplicate (§24)."""
    if o.get("kind") != "evidence":
        return None
    h = o.get("content_hash")
    return f"hash:{h}" if h else None


def _source_of(o: dict[str, Any]) -> str | None:
    s = o.get("source")
    return s if isinstance(s, str) else None


def _provenance(o: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    s = _source_of(o)
    if s:
        refs.append(f"source:{s}")
    for ev in o.get("evidence", ()) or ():
        if isinstance(ev, str):
            refs.append(f"evidence:{ev}")
    return refs


# ---- schema ----------------------------------------------------------------
@dataclass
class EnvelopeItem:
    object_id: str
    kind: str
    text: str
    tokens: int
    role: str                       # contradiction | current | decision | support | history
    provenance: list[str] = field(default_factory=list)


@dataclass
class RedundancyGroup:
    """A collapsed group: one canonical id delivered, the rest reachable behind a handle, with all
    provenance kept. ``kind`` is ``collapsed_history`` or ``duplicate``."""

    kind: str
    canonical: str
    collapsed: list[str]            # folded ids (superseded versions or duplicate copies)
    handle: str
    sources: list[str]              # every distinct source across the group (corroboration kept)
    tokens_saved: int


@dataclass
class ContextEnvelope:
    """EPCTX/1 — evidence-preserving, honest about omissions."""

    query: str
    intent: str
    intent_confidence: str
    items: list[EnvelopeItem]
    pinned_contradictions: list[str]
    collapsed_groups: list[RedundancyGroup]
    provenance_refs: list[str]
    temporal_summary: dict[str, Any]
    context_incomplete: bool
    incomplete_reasons: list[str]
    token_estimate: int
    at_tx: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def object_ids(self) -> list[str]:
        """Ids DELIVERED inline (not those reachable only behind a handle)."""
        return [i.object_id for i in self.items]

    def reachable_ids(self) -> set[str]:
        """Every id the agent can reach — delivered inline OR collapsed behind a handle (recoverable
        without another retrieval). Collapsing is not losing; recall is measured against this."""
        out = set(self.object_ids())
        for g in self.collapsed_groups:
            out.update(g.collapsed)
            out.add(g.canonical)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "EPCTX/1", "query": self.query, "intent": self.intent,
            "intent_confidence": self.intent_confidence,
            "items": [{"object": i.object_id, "kind": i.kind, "role": i.role,
                       "tokens": i.tokens, "provenance": i.provenance} for i in self.items],
            "pinned_contradictions": self.pinned_contradictions,
            "collapsed_groups": [{"kind": g.kind, "current": g.canonical, "collapsed": g.collapsed,
                                  "handle": g.handle, "sources": g.sources,
                                  "tokens_saved": g.tokens_saved} for g in self.collapsed_groups],
            "provenance_refs": self.provenance_refs,
            "temporal_summary": self.temporal_summary,
            "context_incomplete": self.context_incomplete,
            "incomplete_reasons": self.incomplete_reasons,
            "token_estimate": self.token_estimate,
            "temporal_slice": {"at_tx": self.at_tx},
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class EnvelopeConfig:
    """Stable knobs default on; experimental ones default off and never drop critical data."""

    pin_contradictions: bool = True
    collapse_redundancy: bool = True
    top_n: int = 12
    # -- experimental (opt-in; ADR-037) --
    budget_pack: bool = False
    token_budget: int | None = None
    continuation: bool = False


_ROLE_RANK = {"contradiction": 0, "current": 1, "decision": 2, "support": 3, "history": 4}


class ContextEnvelopeBuilder:
    """Build an evidence-preserving Context Envelope over the current authorized retrieval."""

    def __init__(self, engine: Engine) -> None:
        self._eng = engine

    def build(self, principal: Principal, query: str | None, *,
              config: EnvelopeConfig | None = None, at_tx: str | None = None,
              intent: str | None = None, intent_confidence: str | None = None) -> ContextEnvelope:
        principal = require_principal(principal)
        cfg = config or EnvelopeConfig()
        if intent is None:
            intent, conf = classify_intent(query)
        else:
            conf = intent_confidence or "high"

        objs, scored = self._authorized_hits(principal, query, pool=max(cfg.top_n * 4, 40),
                                              at_tx=at_tx)
        reasons: list[str] = []
        groups: list[RedundancyGroup] = []
        keep = objs
        if cfg.collapse_redundancy:
            keep, groups, reasons = self._collapse(objs, scored, intent, conf)

        items = [self._item(o, scored) for o in keep]

        # contradiction pinning: every contradiction retrieved OR attached to a retrieved claim is
        # delivered (a private one is filtered by is_readable inside _contradictions).
        contra_objs = self._contradictions(principal, objs) if cfg.pin_contradictions else []
        pinned = [o["id"] for o in contra_objs]
        present = {i.object_id for i in items}
        for o in contra_objs:
            if o["id"] not in present:
                items.append(self._item(o, scored))
                present.add(o["id"])

        dropped: list[EnvelopeItem] = []
        if cfg.budget_pack and cfg.token_budget is not None:
            items, dropped = self._pack(items, cfg.token_budget, cfg.continuation, pinned)
            if dropped:
                reasons.append("token_limit")
                if cfg.continuation:
                    reasons.append("continuation_available")

        items.sort(key=lambda i: (_ROLE_RANK.get(i.role, 5), i.object_id))
        return self._finalize(query, intent, conf, items, pinned, groups, dropped, reasons, at_tx,
                              objs)

    # -- authorized candidate pool (retrieval unchanged) --------------------
    def _authorized_hits(self, principal: Principal, query: str | None, *, pool: int,
                         at_tx: str | None) -> tuple[list[dict[str, Any]], dict[str, float]]:
        hits = self._eng.search(principal, text=query, limit=pool, at_tx=at_tx,
                                believed_only=False)
        objs: list[dict[str, Any]] = []
        scored: dict[str, float] = {}
        for h in hits:
            o = self._eng.store.get_object(h.get("id", ""))
            if o is None or o.get("kind") in _SKIP_KINDS:
                continue
            if not self._eng.is_readable(principal, o):
                continue  # defense-in-depth; search already firewalled
            objs.append(o)
            scored[o["id"]] = float(h.get("score", 0.0))
        return objs, scored

    def _contradictions(self, principal: Principal, objs: list[dict[str, Any]]
                        ) -> list[dict[str, Any]]:
        """Contradictions to pin: those retrieved, plus those attached to a retrieved claim via an
        evidence-link (contradicts/weakens). Each is is_readable-gated, so a private contradiction
        attached to a readable claim is never surfaced (PRIVATE_CONTRADICTION_LEAK = 0)."""
        found: dict[str, dict[str, Any]] = {o["id"]: o for o in objs if _is_contradiction(o)}
        for o in objs:
            if o.get("kind") != "claim":
                continue
            for link in o.get("metadata", {}).get("evidence_links", []) or ():
                if link.get("relation") not in ("contradicts", "weakens"):
                    continue
                ev_id = link.get("evidence")
                if not isinstance(ev_id, str) or ev_id in found:
                    continue
                ev = self._eng.store.get_object(ev_id)
                if ev is not None and self._eng.is_readable(principal, ev):
                    found[ev_id] = ev
        return list(found.values())

    # -- safe redundancy collapse -------------------------------------------
    def _collapse(self, objs: list[dict[str, Any]], scored: dict[str, float], intent: str,
                  conf: str) -> tuple[list[dict[str, Any]], list[RedundancyGroup], list[str]]:
        groups: list[RedundancyGroup] = []
        reasons: list[str] = []
        collapse_hist = _may_collapse_history(intent, conf)

        # 1) temporal: superseded versions of one statement → keep CURRENT, fold priors (only when
        #    the intent is confidently current AND no version is a contradiction).
        by_stmt: dict[str, list[dict[str, Any]]] = {}
        rest: list[dict[str, Any]] = []
        for o in objs:
            k = _statement_key(o)
            if k:
                by_stmt.setdefault(k, []).append(o)
            else:
                rest.append(o)
        keep: list[dict[str, Any]] = []
        for versions in by_stmt.values():
            multi = len(versions) > 1
            if multi and collapse_hist and not any(_is_contradiction(v) for v in versions):
                current = next((v for v in versions if _is_current(v)),
                               max(versions, key=lambda v: scored.get(v["id"], 0.0)))
                priors = [v for v in versions if v["id"] != current["id"]]
                keep.append(current)
                saved = sum(estimate_tokens(_serialize(v)) for v in priors)
                groups.append(RedundancyGroup(
                    "collapsed_history", current["id"], [v["id"] for v in priors],
                    f"history://{current['id']}", sorted({s for v in versions
                                                          if (s := _source_of(v))}), saved))
                reasons.append("history_collapsed")
            else:
                keep.extend(versions)

        # 2) true duplicates (identical content_hash): show content once, KEEP all sources
        #    (corroboration ≠ duplicate). Contradictions are never duplicate-collapsed.
        by_content: dict[str, list[dict[str, Any]]] = {}
        final: list[dict[str, Any]] = []
        for o in [*keep, *rest]:
            ck = _content_key(o)
            if ck and not _is_contradiction(o):
                by_content.setdefault(ck, []).append(o)
            else:
                final.append(o)
        for dups in by_content.values():
            if len(dups) > 1:
                rep = max(dups, key=lambda v: scored.get(v["id"], 0.0))
                others = [d["id"] for d in dups if d["id"] != rep["id"]]
                final.append(rep)
                saved = sum(estimate_tokens(_serialize(d)) for d in dups if d["id"] != rep["id"])
                groups.append(RedundancyGroup(
                    "duplicate", rep["id"], others, f"expand://{rep['id']}",
                    sorted({s for d in dups if (s := _source_of(d))}), saved))
            else:
                final.extend(dups)
        return final, groups, reasons

    # -- item construction ---------------------------------------------------
    def _item(self, o: dict[str, Any], scored: dict[str, float]) -> EnvelopeItem:
        if _is_contradiction(o):
            role = "contradiction"
        elif o.get("kind") == "decision":
            role = "decision"
        elif not _is_current(o):
            role = "history"
        elif o.get("kind") in ("fact", "claim"):
            role = "current"
        else:
            role = "support"
        text = _serialize(o)
        return EnvelopeItem(o["id"], str(o.get("kind", "object")), text, estimate_tokens(text),
                            role, _provenance(o))

    # -- experimental token-budget packing (ADR-037) ------------------------
    def _pack(self, items: list[EnvelopeItem], budget: int, continuation: bool,
              pinned: list[str]) -> tuple[list[EnvelopeItem], list[EnvelopeItem]]:
        # critical roles (contradiction/current/decision) and pinned contradictions are always kept,
        # even over budget — the budget can never remove critical evidence (§33).
        pinset = set(pinned)
        items.sort(key=lambda i: (_ROLE_RANK.get(i.role, 5), i.object_id))
        effective = int(budget * 0.5) if continuation else budget
        chosen: list[EnvelopeItem] = []
        dropped: list[EnvelopeItem] = []
        used = 0
        for i in items:
            must = i.role in ("contradiction", "current", "decision") or i.object_id in pinset
            if used + i.tokens <= effective or must:
                chosen.append(i)
                used += i.tokens
            else:
                dropped.append(i)
        return chosen, dropped

    def _finalize(self, query: str | None, intent: str, conf: str, items: list[EnvelopeItem],
                  pinned: list[str], groups: list[RedundancyGroup], dropped: list[EnvelopeItem],
                  reasons: list[str], at_tx: str | None,
                  objs: list[dict[str, Any]]) -> ContextEnvelope:
        delivered = {i.object_id for i in items}
        # honesty: a pinned contradiction that is not delivered is a real loss we must declare
        contra_missing = [c for c in pinned if c not in delivered]
        if contra_missing:
            reasons.append("contradiction_unavailable")
        incomplete = bool(dropped) or bool(contra_missing) or "history_collapsed" in reasons \
            or "token_limit" in reasons
        temporal = {
            "collapsed_versions": sum(len(g.collapsed) for g in groups if g.kind
                                      == "collapsed_history"),
            "duplicates_folded": sum(len(g.collapsed) for g in groups if g.kind == "duplicate"),
        }
        prov = sorted({p for i in items for p in i.provenance}
                      | {f"source:{s}" for g in groups for s in g.sources})
        return ContextEnvelope(
            query=query or "", intent=intent, intent_confidence=conf, items=items,
            pinned_contradictions=[c for c in pinned if c in delivered],
            collapsed_groups=groups, provenance_refs=prov, temporal_summary=temporal,
            context_incomplete=incomplete, incomplete_reasons=sorted(set(reasons)),
            token_estimate=sum(i.tokens for i in items), at_tx=at_tx)
