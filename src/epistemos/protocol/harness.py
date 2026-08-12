"""Generic agent harness (mission §14) and reference models (§16).

:class:`GenericAgentHarness` is a *reference consumer*, not a product. It proves any agent, over
any transport, can: request context, inspect completeness, read contradictions explicitly, consume
provenance, and request expansion when offered — with no EPISTEMOS internals and no dependency on
NOMOS / Hermes / OpenClaw.

The models are deterministic and offline (§16): :class:`NullChatModel` proves the protocol needs no
model at all; :class:`FakeChatModel` is a fixed, provider-agnostic reasoner used to exercise
rendering and to run the agent-in-the-loop benchmark without calling any real provider.
"""

from __future__ import annotations

from typing import Any

from ..providers import ModelUnavailableError
from .client import GenericContextClient
from .renderer import RenderStyle, render_prompt

__all__ = ["NullChatModel", "FakeChatModel", "GenericAgentHarness"]


class NullChatModel:
    """No model. Any attempt to generate fails loudly — the protocol itself must not need one."""

    name = "null-chat"

    def complete(self, prompt: str) -> str:
        raise ModelUnavailableError("NullChatModel cannot generate; EPCTX needs no model")


class FakeChatModel:
    """Deterministic, offline reasoner over a rendered prompt. It does not read meaning; it reads
    the structured markers the renderer emits, so output is a reproducible function of input.
    A stand-in for a real model in tests and the benchmark — never a real provider."""

    name = "fake-chat"

    def complete(self, prompt: str) -> str:
        disputed = "DISPUTED" in prompt
        incomplete = "CONTEXT IS INCOMPLETE" in prompt
        historical = "(historical)" in prompt
        facts = [ln for ln in prompt.splitlines() if ln.startswith("[fact]")]
        answer = facts[0][len("[fact]"):].strip() if facts else "no current fact in context"
        notes = []
        if disputed:
            notes.append("DISPUTED")
        if incomplete:
            notes.append("INCOMPLETE")
        if historical:
            notes.append("HISTORICAL_PRESENT")
        return answer + (f" [{','.join(notes)}]" if notes else "")


class GenericAgentHarness:
    """A minimal consumer built only on :class:`GenericContextClient`."""

    def __init__(self, client: GenericContextClient, *, model: Any | None = None,
                 style: RenderStyle = RenderStyle.BALANCED) -> None:
        self._client = client
        self._model = model or FakeChatModel()
        self._style = style

    def consult(self, query: str | None, *, system: str = "Answer only from CONTEXT.",
                user: str | None = None, intent: str | None = None, as_of: str | None = None,
                requested_budget: int | None = None, follow_expansion: bool = False
                ) -> dict[str, Any]:
        """Full consumption cycle. Returns a structured report an agent can act on — the safety
        signals (disputed / incomplete / provenance) come from the document directly, not inferred
        from the model output, so they hold regardless of how good the model is."""
        doc = self._client.context(query, intent=intent, as_of=as_of,
                                   requested_budget=requested_budget)
        contradictions = doc.get("contradictions", [])
        completeness = doc.get("completeness", {})
        prompt = render_prompt(system, doc, user or (query or ""), self._style)
        answer = self._model.complete(prompt)

        expanded: dict[str, Any] | None = None
        expansion = doc.get("expansion", {})
        if follow_expansion and expansion.get("available"):
            handle = expansion["handles"][0]["handle"]
            expanded = self._client.expand(handle)

        return {
            "query": query,
            "answer": answer,
            "disputed": bool(contradictions),
            "contradiction_count": len(contradictions),
            "complete": bool(completeness.get("complete", True)),
            "incomplete_reasons": completeness.get("reasons", []),
            "has_provenance": bool(doc.get("provenance", {}).get("items")),
            "temporal": doc.get("temporal", {}),
            "token_estimate": doc.get("token_estimate"),
            "protocol_version": doc.get("protocol_version"),
            "expanded": expanded,
        }
