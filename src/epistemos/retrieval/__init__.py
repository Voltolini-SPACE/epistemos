"""Explainable retrieval (mission §15).

No single black box. Retrieval is a transparent weighted combination of independent
scorers, and every result carries its ``score_components``, the ``path`` by which it was
found, its ``source``, its ``temporal_state`` and a human-readable ``why``. The default
path uses **no model** (deterministic lexical + temporal + authority signals), so
explainable retrieval works under :class:`~epistemos.providers.NullModelProvider`.

Scorers (each in [0,1], combined by configurable weights):

* ``lexical``  — TF·IDF overlap between the query terms and the object's text.
* ``exact``    — exact subject/predicate/object matches.
* ``recency``  — how recently the object was asserted (transaction time).
* ``authority``— trust of the backing source.
* ``temporal`` — whether the fact is currently believed and valid (or 0 if not).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .._util import now_utc, parse_instant
from ..storage import Store
from ..temporal import believed_at, valid_at

__all__ = ["Retrieved", "Weights", "Retriever"]

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokens(text: str | None) -> list[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _object_text(obj: dict[str, Any]) -> str:
    kind = obj.get("kind")
    if kind == "fact":
        parts = [obj.get("subject"), obj.get("predicate"), obj.get("object")]
    elif kind == "entity":
        parts = [obj.get("name"), obj.get("entity_type"), *obj.get("aliases", [])]
    elif kind == "document":
        parts = [obj.get("title"), obj.get("text")]
    elif kind == "decision":
        parts = [obj.get("statement"), obj.get("outcome")]
    elif kind == "episode":
        parts = [obj.get("summary")]
    elif kind == "observation":
        parts = [obj.get("text")]
    else:
        parts = [obj.get("id")]
    return " ".join(str(p) for p in parts if p)


@dataclass(frozen=True, slots=True)
class Weights:
    lexical: float = 1.0
    exact: float = 1.5
    recency: float = 0.4
    authority: float = 0.6
    temporal: float = 0.8


@dataclass(frozen=True, slots=True)
class Retrieved:
    id: str
    kind: str
    score: float
    score_components: dict[str, float]
    source: dict[str, Any] | None
    temporal_state: dict[str, Any] | None
    why: str
    obj: dict[str, Any] = field(repr=False)


class Retriever:
    def __init__(self, weights: Weights | None = None) -> None:
        self.weights = weights or Weights()

    def search(
        self,
        store: Store,
        tenant: str,
        namespace: str,
        *,
        text: str | None = None,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,  # noqa: A002
        kinds: tuple[str, ...] | None = None,
        limit: int = 10,
        believed_only: bool = False,
        at_tx: str | datetime | None = None,
        at_valid: str | datetime | None = None,
    ) -> list[Retrieved]:
        now = now_utc()
        query_terms = _tokens(text)

        candidates: list[dict[str, Any]] = []
        for obj in store.objects(tenant, namespace):
            if kinds is not None and obj.get("kind") not in kinds:
                continue
            if believed_only and obj.get("kind") == "fact" and obj.get("tx_to") is not None:
                continue
            candidates.append(obj)

        # IDF over the candidate corpus (deterministic; no model).
        df: dict[str, int] = {}
        doc_tokens: dict[str, list[str]] = {}
        for obj in candidates:
            toks = _tokens(_object_text(obj))
            doc_tokens[obj["id"]] = toks
            for term in set(toks):
                df[term] = df.get(term, 0) + 1
        n_docs = max(1, len(candidates))

        trust_cache: dict[str, float] = {}

        def _trust(src_id: str | None) -> float:
            if not src_id:
                return 0.0
            if src_id not in trust_cache:
                src = store.get_object(src_id)
                trust_cache[src_id] = float(src.get("trust", 0.0)) if src is not None else 0.0
            return trust_cache[src_id]

        results: list[Retrieved] = []
        for obj in candidates:
            comp = self._score_one(
                obj,
                query_terms=query_terms,
                subject=subject,
                predicate=predicate,
                object=object,
                doc_tokens=doc_tokens.get(obj["id"], []),
                df=df,
                n_docs=n_docs,
                now=now,
                at_tx=at_tx,
                at_valid=at_valid,
                source_trust=_trust(obj.get("source")),
            )
            total = sum(getattr(self.weights, k) * v for k, v in comp.items())
            if total <= 0.0:
                continue
            results.append(self._build(store, obj, total, comp))

        results.sort(key=lambda r: (r.score, r.id), reverse=True)
        return results[:limit]

    # -- scoring -------------------------------------------------------------
    def _score_one(
        self,
        obj: dict[str, Any],
        *,
        query_terms: list[str],
        subject: str | None,
        predicate: str | None,
        object: str | None,  # noqa: A002
        doc_tokens: list[str],
        df: dict[str, int],
        n_docs: int,
        now: datetime,
        at_tx: str | datetime | None,
        at_valid: str | datetime | None,
        source_trust: float = 0.0,
    ) -> dict[str, float]:
        comp: dict[str, float] = {}

        # lexical TF·IDF (normalized to [0,1] by query length)
        if query_terms:
            score = 0.0
            for term in query_terms:
                tf = doc_tokens.count(term)
                if tf:
                    idf = math.log((n_docs + 1) / (df.get(term, 0) + 1)) + 1.0
                    score += (tf / (tf + 1.0)) * idf
            max_possible = sum(
                math.log((n_docs + 1) / 1) + 1.0 for _ in query_terms
            )
            comp["lexical"] = min(1.0, score / max_possible) if max_possible else 0.0

        # exact structural matches (facts)
        exact = 0.0
        if obj.get("kind") == "fact":
            hits = 0
            asked = 0
            for key, want in (("subject", subject), ("predicate", predicate), ("object", object)):
                if want is not None:
                    asked += 1
                    if obj.get(key) == want:
                        hits += 1
            if asked:
                exact = hits / asked
        if exact:
            comp["exact"] = exact

        # recency by transaction time
        tx_from = parse_instant(obj.get("tx_from") or obj.get("created_at"))
        if tx_from is not None:
            age_days = max(0.0, (now - tx_from).total_seconds() / 86400.0)
            comp["recency"] = 1.0 / (1.0 + age_days / 30.0)  # ~half-life a month

        # authority: trust of the backing source
        if source_trust:
            comp["authority"] = float(source_trust)

        # temporal state (facts): believed AND valid -> 1, else 0
        if obj.get("kind") == "fact":
            ok = believed_at(obj, at_tx) and valid_at(obj, at_valid)
            comp["temporal"] = 1.0 if ok else 0.0

        return comp

    def _build(
        self, store: Store, obj: dict[str, Any], total: float, comp: dict[str, float]
    ) -> Retrieved:
        source_view = None
        src_id = obj.get("source")
        if src_id:
            src = store.get_object(src_id)
            if src is not None:
                source_view = {"id": src["id"], "uri": src.get("uri"), "trust": src.get("trust")}
        temporal_state = None
        if obj.get("kind") == "fact":
            temporal_state = {
                "valid_from": obj.get("valid_from"),
                "valid_to": obj.get("valid_to"),
                "tx_from": obj.get("tx_from"),
                "tx_to": obj.get("tx_to"),
                "believed": obj.get("tx_to") is None,
            }
        why = self._why(comp, temporal_state)
        return Retrieved(
            id=obj["id"],
            kind=obj.get("kind", "unknown"),
            score=round(total, 6),
            score_components={k: round(v, 6) for k, v in comp.items()},
            source=source_view,
            temporal_state=temporal_state,
            why=why,
            obj=obj,
        )

    @staticmethod
    def _why(comp: dict[str, float], temporal_state: dict[str, Any] | None) -> str:
        bits = []
        if comp.get("exact"):
            bits.append("exact structural match")
        if comp.get("lexical"):
            bits.append(f"lexical overlap {comp['lexical']:.2f}")
        if comp.get("authority"):
            bits.append(f"source trust {comp['authority']:.2f}")
        if comp.get("recency"):
            bits.append(f"recency {comp['recency']:.2f}")
        if temporal_state is not None:
            if comp.get("temporal"):
                bits.append("currently believed & valid")
            else:
                bits.append("NOT currently believed/valid (historical)")
        return "; ".join(bits) if bits else "matched query scope"
