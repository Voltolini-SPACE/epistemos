"""Substitutable search-index layer (EPISTEMOS-02, ADR-016).

The index is a **rebuildable projection of the authoritative state (ledger + primary store)**,
never a source of truth. Ports:

* :class:`LexicalIndex` — exact/tokenized/phrase term search (implemented: FTS5 + scan fallback).
* :class:`VectorIndex` — OPTIONAL ANN search boundary (design stub; no default/model/egress).
* :class:`HybridIndex` — OPTIONAL explicit combination of lexical/vector/graph/temporal/authority/
  recency (design stub; ADR-020).

A conforming :class:`LexicalIndex` is **tenant/namespace-aware at the query boundary** (it must not
return rows outside the requested scope), indexes **all** temporal versions (so historical `as_of`
search works — temporal filtering is applied by the retriever over the small candidate set), and
reports its :class:`IndexHealth` so callers can fall back safely instead of returning stale data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "IndexHealth",
    "LexicalIndex",
    "VectorIndex",
    "NullVectorIndex",
    "HybridScoring",
]


class IndexHealth(StrEnum):
    HEALTHY = "INDEX_HEALTHY"  # consistent with authoritative state; safe to use
    DEGRADED = "INDEX_DEGRADED"  # drift/error detected; DO NOT use — fall back to scan
    REBUILDING = "INDEX_REBUILDING"  # rebuild in progress; fall back to scan
    UNAVAILABLE = "INDEX_UNAVAILABLE"  # backend not present (e.g. no FTS5)


class LexicalIndex(ABC):
    """A rebuildable, tenant-aware lexical (term) index over the primary store."""

    @abstractmethod
    def reindex(self, obj: dict[str, Any]) -> None:
        """Insert/update the searchable text for one object. Idempotent."""

    @abstractmethod
    def remove(self, obj_id: str) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def search(
        self,
        tenant: str,
        namespace: str,
        text: str,
        *,
        kinds: tuple[str, ...] | None = None,
        limit: int = 500,
    ) -> list[tuple[str, float]]:
        """Return ``[(obj_id, lexical_score in [0,1])]`` for objects in ``(tenant, namespace)``
        whose indexed text matches ``text``. MUST NOT return out-of-scope rows."""

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def health(self) -> IndexHealth: ...

    @abstractmethod
    def verify(self, store: Any) -> bool:
        """True iff the index set matches the authoritative searchable-object set."""

    @abstractmethod
    def rebuild(self, store: Any) -> int:
        """Drop and rebuild the index from the authoritative store. Returns objects indexed."""


# --- OPTIONAL vector boundary (design only; core passes 100% without it) --------------------
@runtime_checkable
class VectorIndex(Protocol):
    """OPTIONAL ANN search. No default implementation ships, no model is downloaded, and the
    core never requires it (VECTOR_OPTIONAL). A real adapter would be added behind this port."""

    def available(self) -> bool: ...

    def upsert(self, obj_id: str, tenant: str, namespace: str, vector: list[float]) -> None: ...

    def search(
        self, tenant: str, namespace: str, vector: list[float], *, limit: int
    ) -> list[tuple[str, float]]: ...


class NullVectorIndex:
    """The default: no vector search. Proves the core is embedding-free."""

    def available(self) -> bool:
        return False

    def upsert(self, obj_id: str, tenant: str, namespace: str, vector: list[float]) -> None:
        raise NotImplementedError("no vector index configured (core requires none)")

    def search(
        self, tenant: str, namespace: str, vector: list[float], *, limit: int
    ) -> list[tuple[str, float]]:
        raise NotImplementedError("no vector index configured (core requires none)")


class HybridScoring:
    """Design-only description of hybrid score combination (ADR-020).

    A future ``HybridRetriever`` combines independent, explicit signals — never a hidden formula.
    The combination is a weighted sum of normalized-[0,1] components, exactly like the lexical
    retriever today, extended with optional ``vector`` and ``graph`` components:

        total = w_lexical*lexical + w_vector*vector + w_graph*graph
              + w_exact*exact + w_temporal*temporal + w_authority*authority + w_recency*recency

    Each component and weight is reported in ``score_components`` so every result stays explainable.
    Vector/graph contribute 0 when their (optional) backends are absent — the lexical+temporal+
    authority core is unchanged. This class is a specification anchor, not an implementation.
    """

    COMPONENTS = (
        "lexical", "vector", "graph", "exact", "temporal", "authority", "recency",
    )
