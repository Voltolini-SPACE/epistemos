"""EPCTX/1 — the EPISTEMOS context protocol (mission EPISTEMOS-09).

A stable, provider-agnostic **consumption contract**. Any agent — local, over REST, or over MCP —
can request context, read its completeness, distinguish claims from facts, see contradictions
explicitly, follow provenance, understand temporal state, and (experimentally) expand collapsed
groups, without knowing a single EPISTEMOS internal and without EPISTEMOS depending on the consumer.

EPISTEMOS provides knowledge, memory, provenance, temporal state, contradictions, and the context
envelope. The consumer decides how to reason, which model to use, and what action to attempt; a
policy engine decides what is allowed. EPISTEMOS never executes an external action, grants a
capability, or mandates a provider.

Public surface:

* :func:`build_epctx` — produce an ``EPCTX/1`` wire document for an authorized principal.
* :class:`GenericContextClient` + :class:`LocalContextClient` / :class:`RestContextClient` /
  :class:`McpContextClient` — one ``.context()`` / ``.expand()`` surface over three transports.
* :func:`render` + :class:`RenderStyle` — optional prompt rendering (data is never instruction).
* :class:`GenericAgentHarness` — a reference consumer proving the contract is enough.
* serialization / versioning / handles — the protocol machinery.
"""

from __future__ import annotations

from .client import (
    GenericContextClient,
    LocalContextClient,
    McpContextClient,
    RestContextClient,
)
from .handles import ExpansionRegistry, registry_for
from .harness import FakeChatModel, GenericAgentHarness, NullChatModel
from .renderer import RenderStyle, render
from .serialize import HASH_ALGO, canonical_json, context_hash
from .versioning import PROTOCOL_VERSION, is_compatible
from .wire import build_epctx, project_object

__all__ = [
    "PROTOCOL_VERSION",
    "build_epctx",
    "project_object",
    "canonical_json",
    "context_hash",
    "HASH_ALGO",
    "is_compatible",
    "GenericContextClient",
    "LocalContextClient",
    "RestContextClient",
    "McpContextClient",
    "render",
    "RenderStyle",
    "GenericAgentHarness",
    "FakeChatModel",
    "NullChatModel",
    "ExpansionRegistry",
    "registry_for",
]
