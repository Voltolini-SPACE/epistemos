# MEMORY MODEL

Memory classes are **semantic types over one ledger-backed store**, not separate databases and not
decorative labels (mission §12, ADR-005). The contract below is machine-readable in
`src/epistemos/memory/SPEC` and asserted by `tests/unit/test_memory.py`.

## The taxonomy

| class | scope | retention | mutable | temporal (bitemporal) | provenance required |
|-------|-------|-----------|:------:|:---------------------:|:-------------------:|
| **working** | session/agent transient | ephemeral (cleared at session end) | yes | no | no |
| **session** | single session | session lifetime | yes | no | no |
| **episodic** | agent | durable, append-only | no | yes | yes |
| **semantic** | tenant/namespace shared | durable, superseded-not-deleted | no | yes | yes |
| **procedural** | tenant/namespace | durable, versioned | no | yes | yes |
| **longterm** | tenant | durable, superseded-not-deleted | no | yes | yes |

These distinctions are **real and enforceable**, not cosmetic: e.g. `working.mutable=True` vs
`semantic.mutable=False`; `working.temporal=False` vs `semantic/episodic.temporal=True`;
`episodic.provenance_required=True` vs `working.provenance_required=False`.

## How each class is expressed

- **Facts** carry a `memory_class` (default `semantic`). `recall(memory_class=…)` filters by it.
- **Episodes** are the unit of **episodic** memory (`remember`/`recall(memory_class=episodic)`),
  time-stamped experiences that can reference the facts distilled from them.
- **Observations** are raw, source-attributed inputs (a natural home for **working**/transient claims
  before they are asserted as durable facts).
- **Session** scoping is available on episodes/observations (`session=…`) and queried via
  `recall(session=…)`.

## Why one store, not four

A single ledger-backed store gives one consistency boundary, one backup, one tamper-evident chain,
and one provenance graph across all memory classes. Splitting into four databases would add
cross-store sync/consistency burden and sever cross-class provenance for no measured benefit
(mission §39). Retention/eviction policy for `working`/`session` is a caller concern in v0.1 (no
auto-eviction daemon); the *semantics* (what each class means, its mutability and provenance
requirement) are enforced now.
