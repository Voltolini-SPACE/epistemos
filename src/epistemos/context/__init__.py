"""Evidence-Preserving Context — the Context Envelope (EPISTEMOS v0.6, ADR-033…037).

EPISTEMOS keeps the whole sovereign, temporal, auditable knowledge base. An agent rarely needs all
of it for one inference. The **Context Envelope** compresses the *transmission* of memory, never the
memory: it takes the objects the current retrieval already returned (authorized, unchanged) and
delivers an evidence-preserving compact context — pinning contradictions, collapsing only *safe*
redundancy (superseded current-state versions, true duplicates), preserving provenance, and
declaring any loss honestly (``context_incomplete``).

    query → authorization → current retrieval → contradiction pinning → redundancy analysis
          → safe collapse → Context Envelope → agent

It never widens the candidate set and never dereferences an unauthorized object; the only relation
it follows (a claim's attached contradiction) is re-authorized against ``Engine.is_readable``.

Stable in v0.6: contradiction pinning, intent-aware safe redundancy collapse, context-incomplete.
Experimental (opt-in, off by default): token-budget packing and continuation handles.
"""

from .builder import (
    ContextEnvelope,
    ContextEnvelopeBuilder,
    EnvelopeConfig,
    EnvelopeItem,
    RedundancyGroup,
    classify_intent,
    estimate_tokens,
)

__all__ = [
    "ContextEnvelope",
    "ContextEnvelopeBuilder",
    "EnvelopeConfig",
    "EnvelopeItem",
    "RedundancyGroup",
    "classify_intent",
    "estimate_tokens",
]
