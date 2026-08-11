"""Graph primitives.

Entities and relations are first-class objects (mission §6). They are created and
traversed through the :class:`~epistemos.core.Engine` (``add_entity``, ``add_relation``,
``neighbors``, ``query_graph``) so that every graph mutation flows through the ledger.
Traversal is bounded (hop limit + node budget) to defend against graph-expansion DoS.

This module intentionally holds no query language: there is no Cypher/SPARQL/Gremlin
surface to inject into. Traversal is expressed as typed method calls with validated
arguments (see ADR-002 / ADR-010).
"""

from __future__ import annotations

from ..model import Entity, Relation

__all__ = ["Entity", "Relation"]
