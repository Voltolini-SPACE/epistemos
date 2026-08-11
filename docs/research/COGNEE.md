# Cognee

**Identity (MEASURED):** `github.com/topoteretes/cognee` (cognee.ai), **Apache-2.0**, Python
(async throughout) + TS SDK + REST. An "AI memory" layer replacing flat RAG with an **ECL
(Extract–Cognify–Load)** pipeline. Embedded local default: SQLite + LanceDB + embedded graph.

**Temporal (MEASURED):** single-timeline; **real bitemporality needs an external tool (Graphiti)**
— not native.

**Provenance (MEASURED):** **document-level only**; LLM-extracted triples carry no per-assertion
evidence pointer or hash.

**Retrieval (MEASURED):** a **typed retrieval enum** (GRAPH_COMPLETION, TEMPORAL, CYPHER, CHUNKS,
TRIPLET, NL) — callers pick a strategy explicitly (nice for explainability).

**Cognify quality gate (MEASURED) — the standout idea:** **ontology/schema-validated** entity +
relationship extraction during ingest, constraining LLM output against a declared schema instead of
trusting free-form output. Measurably raises graph quality over naive RAG.

**Security (MEASURED):** access control / multi-tenant isolation is **OFF by default** (opt-in) —
the opposite of fail-closed. Three separate stores (graph/vector/relational) with **no cross-store
transaction** → a mid-pipeline failure leaves them inconsistent.

## What it got right (KEEP)
ECL as an explicit, composable pipeline · ontology-validated extraction as a quality gate ·
storage-agnostic adapter interfaces · embedded local-first default stack · typed retrieval enum.

## What we reject
Opt-in (not fail-closed) access control · cloud LLM as default extraction path · document-level-only
provenance · bolt-on bitemporality · non-transactional multi-store writes with no rebuild path.

## The one lesson for EPISTEMOS
Keep an **ontology/schema-validated extraction gate** — but make it **deterministic and
provenance-anchored**: every validated assertion must carry a source span + hash. (In EPISTEMOS the
gate is caller-side today; the *contract* — validated, provenance-carrying assertions — is enforced.)

## How EPISTEMOS differs
Single crash-consistent store with atomic transactions and a ledger-rebuildable projection (vs
three unsynchronized stores); **fail-closed** isolation by default; native bitemporality;
per-assertion provenance with content hashes.
