"""Decision lineage (mission §13, §11).

A :class:`~epistemos.model.Decision` records a statement, the evidence (fact/observation
ids) that supports it, the alternatives considered, the outcome and whether it is
reversible. ``Engine.record_decision`` validates that every evidence id resolves inside
the caller's scope, so decision lineage is never dangling. ``Engine.explain(decision_id)``
answers *WHAT EVIDENCE LED TO THIS DECISION?* by walking the evidence provenance.
"""

from __future__ import annotations

from ..model import Decision
from ..provenance import explain_decision

__all__ = ["Decision", "explain_decision"]
