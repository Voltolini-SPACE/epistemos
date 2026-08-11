"""LLM / embedding boundary (mission §16).

The core performs **no** model calls for any fundamental operation (get, put, retract,
timeline, graph traversal, exact query, metadata query). Models are optional and reach
the system only through :class:`ModelProvider`. The presence and correctness of
:class:`NullModelProvider` is the proof that the core runs with no model at all
(the ``NULL_LLM_MODE`` gate).

A provider may participate in *optional* enrichment: entity/relation extraction,
summarization, ontology proposal, entity resolution, query interpretation, embeddings.
None of these are on the core read/write path.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..errors import EpistemosError

__all__ = ["ModelProvider", "NullModelProvider", "ModelUnavailableError"]


class ModelUnavailableError(EpistemosError):
    """Raised when model-dependent enrichment is requested but no model is available."""


@runtime_checkable
class ModelProvider(Protocol):
    """Optional model capabilities. All methods are enrichment, never core operations."""

    name: str

    def available(self) -> bool: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def extract_triples(self, text: str) -> list[tuple[str, str, str | None]]: ...

    def summarize(self, text: str) -> str: ...


class NullModelProvider:
    """The default provider: no model, no network, no capability.

    Every enrichment method fails loudly so that any code path which *requires* a model
    is impossible to reach silently. Core operations never call these.
    """

    name = "null"

    def available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ModelUnavailableError("NullModelProvider cannot embed; core requires no embeddings")

    def extract_triples(self, text: str) -> list[tuple[str, str, str | None]]:
        raise ModelUnavailableError("NullModelProvider cannot extract; supply triples explicitly")

    def summarize(self, text: str) -> str:
        raise ModelUnavailableError("NullModelProvider cannot summarize")
