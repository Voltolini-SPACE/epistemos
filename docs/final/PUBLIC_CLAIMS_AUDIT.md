# EPISTEMOS — Public Claims Audit (Freeze 2026.08)

Every load-bearing public claim, classified and traced to evidence. Classification:
**PROVEN** (enforced by code + test), **MEASURED** (benchmark with reproducible method),
**INFERRED** (positioning, not a testable assertion), **ROADMAP** (future/planned, disclosed as
such), **REMOVE** (overclaim — deleted or softened).

| Claim | Classification | Evidence |
|---|---|---|
| Zero-egress (core makes no network calls) | PROVEN | `tests/security/test_zero_egress.py` traps `socket`/`create_connection` across the lifecycle; `test_source_uri_is_never_dereferenced`. Scoped to *core*; REST/MCP/SDK transports are opt-in and disclosed. |
| No mandatory LLM (`NullModelProvider`) | PROVEN | `providers/__init__.py`; `NULL_LLM_MODE` gate, `tests/unit/test_null_llm.py`. |
| MIT licensed, everywhere | PROVEN | `LICENSE`, `pyproject.toml`. Relicensed from Apache-2.0 in v0.4 (ADR-027); only Apache mention is a dev-only transitive + the historical ADR, both justified. |
| Zero runtime dependencies (stdlib only) | PROVEN | `pyproject.toml` `dependencies = []`. |
| Bitemporal (valid + transaction time) | PROVEN | `tests/unit/test_temporal.py`; ADR-003. |
| Tamper-evident hash-chained ledger | PROVEN | `tests/unit/test_ledger.py` (9 attacks + anchors). |
| Multi-tenant, fail-closed | PROVEN | `tests/security/test_tenant_isolation.py`, `test_agent_isolation.py`. |
| Provenance-first, `explain()` genealogy | PROVEN | `tests/unit/test_provenance.py`; ADR-004; W3C PROV mapping. |
| Claims / evidence / reviews; belief derived; majority ≠ truth | PROVEN | `tests/claims/`; ADR-028/029; `claims/belief.py`. |
| Knowledge Spaces, private-by-default; `PRIVATE_TO_PUBLIC_LEAK=0` | PROVEN | `tests/spaces/`, `test_private_public_invariant.py`. |
| EPCTX/1 provider-agnostic, 3 transports, parity | PROVEN | `tests/protocol/test_protocol.py`, `test_local_rest_mcp_equivalent`. |
| `PRIVATE_EPCTX / PRIVATE_EXPANSION / CROSS_TENANT_EPCTX = 0` | PROVEN | `tests/protocol/test_protocol_security.py`. |
| Panel local-first, `is_readable`-gated; UI/graph/search/stream leak = 0 | PROVEN | `tests/panel/test_leak.py`; strict `default-src 'self'` CSP. |
| Panel v1.1 hardening (no future-knowledge leak, anti-smuggling, inert render) | PROVEN | `docs/panel/hardening/HARDENING_REPORT.md`; `test_bitemporal.py::test_future_knowledge_leak_is_zero`. |
| **1063 tests**, ruff + mypy `--strict` clean | PROVEN | Collection = 1063 under **both** `pytest` and `python -m pytest` (the bare form used to fail — see corrections below). Ruff is clean over the **whole repository**, not only `src/`. Re-verified by CI on every push. |
| Mutation 39/39 core · 9/9 panel · 6/6 envelope · 7/7 EPCTX | PROVEN / MEASURED | `tools/mutation_harness.py`, `mutation_panel.py`, `eps08_mutation.py`, `eps09_mutation.py`. |
| 100k lexical search **~146× (5.0 s → 34 ms)** via FTS5 | MEASURED | `docs/benchmarks/EPISTEMOS_02_FINAL_BENCHMARK.md` — re-run 2026-08-22, reference hardware, single authoritative table. Supersedes the earlier `183× (6.2 s → 34 ms)`, which quoted a different run than the file it linked. The speedup is host-dependent; the order of magnitude is not. |
| `explain()` ~33,800× at 100k (~1.9 s → 0.05 ms) | MEASURED | `EPISTEMOS_03_FINAL_BENCHMARK.md`; ADR-022. |
| Context Envelope **up to ~35% fewer tokens in measured redundant workloads**, "not universal" | MEASURED, qualified | `docs/context/BENCHMARK.md`; `tools/eps08_benchmark.py`. Qualified on README + site. |
| "Turn information into auditable knowledge" (tagline) | INFERRED | Positioning, not a testable assertion. |
| NOMOS / Hermes / OpenClaw integration | ROADMAP | Spec-only (`docs/integrations/`); suite runs with none imported. Disclosed as planned/adapter-ready, never as shipped. |
| ~~"the only surveyed design that is simultaneously bitemporal, deterministic, hash-anchored, fail-closed, explainable, local-first"~~ | **REMOVE** | Falsified 2026-08-22. Six peer projects make the same combination of claims (statewave, mnemos, talamus, verimem, cormex, Mneme). The original census surveyed only the large LLM-native systems. Claim now scoped to tier 1 explicitly; see `docs/research/COMPETITOR_MATRIX.md` §Tier 2. |
| Semantic / vector retrieval | **NOT SHIPPED** | `VectorIndex` is a Protocol; only `NullVectorIndex` is implemented. Disclosed in `docs/KNOWN_LIMITATIONS.md`. Never claimed on any surface. |
| Deterministic ingestion — text compiles to **candidate claims**, never accepted truth | PROVEN | `Engine.compile_document` / `epistemos compile`; `tests/unit/test_ingest.py` (compiled claims are `proposed`, `current()` stays `None`), `tests/security/test_ingest_isolation.py`. No model, no network: runs under `NullModelProvider` and under a socket trap. |
| Compiled claims are byte-reproducible and idempotent | PROVEN | `test_compilation_is_byte_reproducible`, `test_recompiling_an_unchanged_document_creates_nothing`. Dedupe key covers (document, source hash, rule, span, triple). |
| Ingestion **recall** on unstructured prose | **LOW BY DESIGN** | The rules read unambiguous structure plus an enumerated set of sentence patterns; prose in an uncovered shape yields nothing, silently (`test_prose_without_a_recognized_shape_yields_nothing`). Disclosed in `docs/KNOWN_LIMITATIONS.md` — this is not a claim of extraction parity with LLM-native systems. |
| Score on LoCoMo / LongMemEval / BEAM | **NONE** | No number published on any shared benchmark, so no public comparison is possible in either direction. Disclosed in `docs/KNOWN_LIMITATIONS.md`. |
| `pip install epistemos` | **NOT AVAILABLE** | Not published to PyPI; install is `git clone` + editable. README says so; no surface implies otherwise. |

## Corrections applied at freeze

1. Site EPISTEMOS page: stale **928** test count → **996** (and mutation line completed to 6/6 + 7/7).
2. README: "**instant**" search → "**fast**" (absolute performance word without a benchmark).
3. Panel label aligned to **v1.1** across README (matches tag/release/site).

## Corrections applied 2026-08-22 (adversarial re-validation)

An independent re-run of every gate on the frozen tree found the code claims sound and the
*evidence chain* broken in two places. Both are now closed:

5. **Benchmark provenance.** The headline read "100k: 6.2 s → 34 ms (~183×)" while the linked
   evidence file measured a different run, and the `183×` printed beside "100k" was in fact the
   **1,000**-scale figure from that file. Two real runs, one citation — a provenance break in the
   shop window of a product that sells traceability. Fixed by re-running
   `benchmarks/compare_retrieval.py` and propagating **one** table to README, site, OG and this
   audit. Where the honest number moved, the honest number was published.
6. **Uniqueness claim retired** (row above). The census had surveyed only tier 1.
7. **`SQLiteStore.backup()` contract corrected, and a real check-then-act race fixed.** The
   docstring promised it was "safe to call concurrently with writers"; the code read the
   transaction depth **outside** the lock and refused whenever a writer happened to be mid-
   transaction. Two consequences: safe backups were rejected under load, and — worse — a writer
   could open a transaction between the check and the backup, producing exactly the `SQLITE_BUSY`
   deadlock (LT-05) the guard existed to prevent. The check now happens while holding the lock, so
   a backup waits for an in-flight writer instead of failing, while a genuinely re-entrant call
   from inside `atomic()` is still refused. This was surfacing as **flaky RACE gates**: the same
   suite produced 4, 12 and 14 failures across runs on the *unmodified* tree. It now passes 360/360
   on repeated runs and under saturated CPU. A gate that only passed when the scheduler cooperated
   was never evidence.

Two defects outside the claim surface were fixed in the same pass: a bare `pytest` invocation
failed to collect (21 errors — the "996 tests" claim was irreproducible for anyone who typed the
canonical command), and the repository had **no CI at all**, so every gate in `docs/STATUS.md` was
verified by hand on one machine. Both now hold: `pythonpath` is declared, and
`.github/workflows/ci.yml` re-runs the suite, the linters, the mutation battery and the wheel build
across 4 Pythons × 2 operating systems on every push.

## Overclaim sweep

No prohibited vocabulary anywhere: no "AI brain", "AGI", "knows everything", "Palantir", "Tesla",
"Einstein", "zero hallucinations", "perfect memory", "at any scale", "instant" (fixed). The token
claim is qualified on every surface. Benchmark numbers always carry context (hardware + method).

**Result: PUBLIC_CLAIMS_AUDIT = PASS.**
