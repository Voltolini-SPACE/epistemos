"""Explainable retrieval (mission §15; EPISTEMOS-02 adds an indexed path).

Two retrievers share **all** scoring and explainability; they differ only in how the candidate
set and the lexical component are obtained:

* :class:`LegacyScanRetriever` — the v0.1 O(N) full-scan with TF·IDF lexical scoring. Reference and
  safe fallback.
* :class:`IndexedRetriever` — gets text candidates from a :class:`~epistemos.index.LexicalIndex`
  (FTS5) in O(matches) and uses its BM25-derived lexical score. Same temporal/authority/exact/
  recency components, same result shape (ADR-016/017).

Every result carries ``score``, ``score_components``, ``source``, ``temporal_state`` and a human
``why_returned``. Source trust (authority) and fact confidence remain separate dimensions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .._util import now_utc, parse_instant
from ..index import LexicalIndex
from ..index.text import object_text, tokens
from ..storage import Store
from ..temporal import believed_at, valid_at

__all__ = ["Retrieved", "Weights", "LegacyScanRetriever", "IndexedRetriever", "Retriever"]

# Retrieve up to this many lexical candidates by relevance, then re-rank by the full score.
# Bounds recall for very high-frequency terms (documented trade-off, ADR-017).
CANDIDATE_POOL = 500


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


# ---------------------------------------------------------------------------
# shared scoring (identical for both retrievers)
# ---------------------------------------------------------------------------
def _nonlexical_components(
    obj: dict[str, Any],
    *,
    subject: str | None,
    predicate: str | None,
    object: str | None,  # noqa: A002
    source_trust: float,
    now: datetime,
    at_tx: str | datetime | None,
    at_valid: str | datetime | None,
) -> dict[str, float]:
    comp: dict[str, float] = {}
    if obj.get("kind") == "fact":
        hits = asked = 0
        for key, want in (("subject", subject), ("predicate", predicate), ("object", object)):
            if want is not None:
                asked += 1
                if obj.get(key) == want:
                    hits += 1
        if asked:
            comp["exact"] = hits / asked
    tx_from = parse_instant(obj.get("tx_from") or obj.get("created_at"))
    if tx_from is not None:
        age_days = max(0.0, (now - tx_from).total_seconds() / 86400.0)
        comp["recency"] = 1.0 / (1.0 + age_days / 30.0)
    if source_trust:
        comp["authority"] = float(source_trust)
    if obj.get("kind") == "fact":
        comp["temporal"] = 1.0 if (believed_at(obj, at_tx) and valid_at(obj, at_valid)) else 0.0
    return comp


def matches_structural(
    obj: dict[str, Any],
    *,
    subject: str | None,
    predicate: str | None,
    object: str | None,  # noqa: A002
) -> bool:
    """Does ``obj`` satisfy every supplied structural constraint?

    A query constraint **filters**; it is not merely a ranking hint. Only facts carry
    subject/predicate/object, so a non-fact can never satisfy one — asking for
    ``subject="Alice"`` among documents is legitimately empty rather than "every document,
    ranked by recency" (EPISTEMOS-03, A-03/A-04; ADR-021).
    """
    if subject is None and predicate is None and object is None:
        return True
    if obj.get("kind") != "fact":
        return False
    return all(
        obj.get(key) == want
        for key, want in (("subject", subject), ("predicate", predicate), ("object", object))
        if want is not None
    )


def _temporal_state(obj: dict[str, Any]) -> dict[str, Any] | None:
    if obj.get("kind") != "fact":
        return None
    return {
        "valid_from": obj.get("valid_from"), "valid_to": obj.get("valid_to"),
        "tx_from": obj.get("tx_from"), "tx_to": obj.get("tx_to"),
        "believed": obj.get("tx_to") is None,
    }


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
        bits.append("currently believed & valid" if comp.get("temporal")
                    else "NOT currently believed/valid (historical)")
    return "; ".join(bits) if bits else "matched query scope"


def _build(store: Store, obj: dict[str, Any], total: float, comp: dict[str, float]) -> Retrieved:
    source_view = None
    src_id = obj.get("source")
    if src_id:
        src = store.get_object(src_id)
        if src is not None:
            source_view = {"id": src["id"], "uri": src.get("uri"), "trust": src.get("trust")}
    ts = _temporal_state(obj)
    return Retrieved(
        id=obj["id"], kind=obj.get("kind", "unknown"), score=round(total, 6),
        score_components={k: round(v, 6) for k, v in comp.items()},
        source=source_view, temporal_state=ts, why=_why(comp, ts), obj=obj,
    )


class _BaseRetriever:
    def __init__(self, weights: Weights | None = None) -> None:
        self.weights = weights or Weights()

    def _total(self, comp: dict[str, float]) -> float:
        return float(sum(
            float(getattr(self.weights, k)) * v
            for k, v in comp.items() if hasattr(self.weights, k)
        ))

    def _trust_lookup(self, store: Store) -> Any:
        cache: dict[str, float] = {}

        def trust_of(obj: dict[str, Any]) -> float:
            src_id = obj.get("source")
            if not src_id:
                return 0.0
            if src_id not in cache:
                src = store.get_object(src_id)
                cache[src_id] = float(src.get("trust", 0.0)) if src is not None else 0.0
            return cache[src_id]

        return trust_of


# ---------------------------------------------------------------------------
# LegacyScanRetriever — v0.1 behavior (reference + fallback), unchanged
# ---------------------------------------------------------------------------
class LegacyScanRetriever(_BaseRetriever):
    def search(
        self, store: Store, tenant: str, namespace: str, *,
        text: str | None = None, subject: str | None = None, predicate: str | None = None,
        object: str | None = None, kinds: tuple[str, ...] | None = None,  # noqa: A002
        limit: int = 10, believed_only: bool = False,
        at_tx: str | datetime | None = None, at_valid: str | datetime | None = None,
    ) -> list[Retrieved]:
        now = now_utc()
        query_terms = tokens(text)
        trust_of = self._trust_lookup(store)

        candidates: list[dict[str, Any]] = []
        for obj in store.objects(tenant, namespace):
            if kinds is not None and obj.get("kind") not in kinds:
                continue
            if believed_only and obj.get("kind") == "fact" and obj.get("tx_to") is not None:
                continue
            if not matches_structural(obj, subject=subject, predicate=predicate, object=object):
                continue
            candidates.append(obj)

        df: dict[str, int] = {}
        doc_tokens: dict[str, list[str]] = {}
        for obj in candidates:
            toks = tokens(object_text(obj))
            doc_tokens[obj["id"]] = toks
            for term in set(toks):
                df[term] = df.get(term, 0) + 1
        n_docs = max(1, len(candidates))

        results: list[Retrieved] = []
        for obj in candidates:
            comp = _nonlexical_components(
                obj, subject=subject, predicate=predicate, object=object,
                source_trust=trust_of(obj), now=now, at_tx=at_tx, at_valid=at_valid,
            )
            if query_terms:
                comp["lexical"] = _tfidf(query_terms, doc_tokens.get(obj["id"], []), df, n_docs)
                if not comp["lexical"]:
                    continue  # a text query that matched no term is not a hit (ADR-021)
            total = self._total(comp)
            if total <= 0.0:
                continue
            results.append(_build(store, obj, total, comp))
        results.sort(key=lambda r: (r.score, r.id), reverse=True)
        return results[:limit]


def _tfidf(query_terms: list[str], doc_tokens: list[str], df: dict[str, int], n_docs: int) -> float:
    score = 0.0
    for term in query_terms:
        tf = doc_tokens.count(term)
        if tf:
            idf = math.log((n_docs + 1) / (df.get(term, 0) + 1)) + 1.0
            score += (tf / (tf + 1.0)) * idf
    max_possible = sum(math.log((n_docs + 1) / 1) + 1.0 for _ in query_terms)
    return float(min(1.0, score / max_possible)) if max_possible else 0.0


# ---------------------------------------------------------------------------
# IndexedRetriever — FTS candidate set, same scoring/explainability
# ---------------------------------------------------------------------------
class IndexedRetriever(_BaseRetriever):
    def __init__(self, index: LexicalIndex, weights: Weights | None = None) -> None:
        super().__init__(weights)
        self.index = index

    def search(
        self, store: Store, tenant: str, namespace: str, *,
        text: str | None = None, subject: str | None = None, predicate: str | None = None,
        object: str | None = None, kinds: tuple[str, ...] | None = None,  # noqa: A002
        limit: int = 10, believed_only: bool = False,
        at_tx: str | datetime | None = None, at_valid: str | datetime | None = None,
    ) -> list[Retrieved]:
        now = now_utc()
        trust_of = self._trust_lookup(store)

        pairs: list[tuple[dict[str, Any], float]] = []
        if text and tokens(text):
            for obj_id, lexical in self.index.search(
                tenant, namespace, text, kinds=kinds, limit=CANDIDATE_POOL
            ):
                obj = store.get_object(obj_id)
                if obj is None or obj.get("tenant") != tenant or obj.get("namespace") != namespace:
                    continue  # defense-in-depth: never surface an out-of-scope object
                if kinds is not None and obj.get("kind") not in kinds:
                    continue
                if believed_only and obj.get("kind") == "fact" and obj.get("tx_to") is not None:
                    continue
                if not matches_structural(obj, subject=subject, predicate=predicate,
                                          object=object):
                    continue
                pairs.append((obj, lexical))
        else:
            # no text -> structural / bounded (fast via indexed columns), no lexical component
            source = store.facts(tenant, namespace, subject=subject, predicate=predicate,
                                 object=object) if (subject or predicate or object) \
                else list(store.objects(tenant, namespace))
            for obj in source:
                if kinds is not None and obj.get("kind") not in kinds:
                    continue
                if believed_only and obj.get("kind") == "fact" and obj.get("tx_to") is not None:
                    continue
                pairs.append((obj, 0.0))

        results: list[Retrieved] = []
        for obj, lexical in pairs:
            comp = _nonlexical_components(
                obj, subject=subject, predicate=predicate, object=object,
                source_trust=trust_of(obj), now=now, at_tx=at_tx, at_valid=at_valid,
            )
            if lexical:
                comp["lexical"] = lexical
            total = self._total(comp)
            if total <= 0.0:
                continue
            results.append(_build(store, obj, total, comp))
        results.sort(key=lambda r: (r.score, r.id), reverse=True)
        return results[:limit]


# Back-compat alias: the default retriever name used by v0.1 code paths.
Retriever = LegacyScanRetriever
