# ADR-002 — Graph model: property graph via typed operations, no query language

**Status:** Accepted (v0.1)

## Context
Entities and relations must be first-class (mission §6). Competitors expose Cypher/SPARQL or
LLM-generated queries, which are injection surfaces (ABI, Graphiti). We also want facts to be
queryable as (subject, predicate, object) triples independent of an entity/relation catalog.

## Decision
A labeled **property graph**: `Entity` (name, type, aliases) and `Relation`
(source_entity, target_entity, rel_type), plus `Fact` triples that can reference entities by id or
name. Traversal is expressed as **typed method calls** (`add_entity`, `add_relation`, `neighbors`,
`query_graph`) with validated arguments and a **bounded BFS** (hop cap + node budget). There is
**no query-language surface** to inject into (S3–S5 are N/A by design).

## Consequences
- No Cypher/SPARQL injection surface; traversal DoS is bounded.
- Rich path queries (arbitrary Cypher) are not available; typed traversal covers v0.1 needs.
- Entity resolution is explicit (ADR: identity), never auto-merged by string similarity.

## Rejected alternatives
- **Embed Cypher/SPARQL** or **LLM→query generation**: injection + over-broad-query risk; rejected.
- **RDF triple store as the core**: heavier, standards-coupled; RDF/PROV kept as an *export* target
  instead (ADR-004, ADR-014).
