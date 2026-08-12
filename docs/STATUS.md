# EPISTEMOS — Gate Matrix & Evidence Ledger

Single honest source of truth for the V0.1 gates (mission §40). A gate is **PASS** only with
specific, reproducible evidence — never because "the suite is green" (§41). `PARTIAL` is never
reported as `PASS`. Full detail: [`EPISTEMOS_V0_1_FINAL_REPORT.md`](EPISTEMOS_V0_1_FINAL_REPORT.md).

Legend: ✅ PASS · 🟡 PARTIAL · ⛔ BLOCKED · ⬜ PENDING

| Gate | State | Evidence |
|------|-------|----------|
| ETAPA0_ISOLATION | ✅ | baseline vs recheck identical; `docs/architecture/ETAPA0_ISOLATION.md` |
| NAMING (internal) | ✅ | exact name free on PyPI/npm/GitHub; `docs/research/NAMING_REPORT.md` |
| PUBLIC_BRAND_CLEARANCE | ⬜ | pending formal trademark search (non-blocking, §AI) |
| CENSUS | ✅ | `docs/research/COMPETITOR_MATRIX.md` (12 systems, live web) |
| FEATURE_HARVEST | ✅ | `docs/research/FEATURE_HARVEST.md` (21 properties) |
| CORE_MODEL | ✅ | `tests/unit/test_model.py`; `docs/spec/CORE_MODEL.md` |
| BITEMPORAL/TEMPORAL | ✅ | `tests/unit/test_temporal.py` (CASO1/CASO2 + half-open boundary) |
| PROVENANCE | ✅ | `tests/unit/test_provenance.py` (multi-hop) |
| CONTRADICTION | ✅ | `tests/unit/test_contradiction.py` (no hard delete) |
| ENTITY_IDENTITY | ✅ | `tests/unit/test_entity_identity.py` (explicit merge/split) |
| MEMORY | ✅ | `tests/unit/test_memory.py`; `docs/spec/MEMORY_MODEL.md` |
| GRAPH | ✅ | conformance flow; bounded traversal |
| RETRIEVAL | ✅ | `tests/unit/test_retrieval.py` (explainable) |
| TENANT_ISOLATION | ✅ | `tests/security/test_tenant_isolation.py` (fail-closed) |
| AGENT_ISOLATION | ✅ | `tests/security/test_agent_isolation.py` |
| ZERO_EGRESS_DEFAULT | ✅ | `tests/security/test_zero_egress.py`; `ZERO_EGRESS_REPORT.md` |
| NULL_LLM_MODE | ✅ | `tests/unit/test_null_llm.py` |
| STORE_CONFORMANCE | ✅ | parametrized over MemoryStore + SQLiteStore |
| ATOMIC_MUTATION | ✅ | `tests/unit/test_atomic.py` (fault injection) |
| LEDGER_TAMPER_EVIDENCE | ✅ | `tests/unit/test_ledger.py` (9 attacks + anchors) |
| CRASH_RECOVERY | ✅ | `tests/chaos/` real SIGKILL |
| PROJECTION_REBUILD | ✅ | `rebuild_projection` == replay (tested) |
| BACKUP_RESTORE | ✅ | `tests/unit/test_backup_restore.py` |
| EXPORT_IMPORT | ✅ | `tests/unit/test_export_import.py` (1-byte tamper detected) |
| SCHEMA_MIGRATION | ✅ | `tests/unit/test_schema_migration.py` |
| SECURITY_BATTERY (S1-S50) | ✅ | `docs/security/THREAT_MODEL.md` + tests; residuals disclosed |
| RACE | ✅ | `tests/race/` (30 cycles/scenario) |
| MUTATION_CRITICAL | ✅ | `tools/mutation_harness.py` → 12/12 killed, 0 survived |
| CHAOS | ✅ | `tests/chaos/` |
| BENCHMARK | ✅ | `docs/benchmarks/RESULTS.md` (search-at-scale = disclosed limitation) |
| QUALITY_CORPUS | ✅ | `tests/unit/test_quality_corpus.py` |
| REST / MCP / SDK | ✅ | `tests/integration/` |
| ADRS (001-015) | ✅ | `docs/adr/` |
| DOCS | ✅ | research + spec + adr + security + integration + benchmarks |
| LICENSES / CLEAN_ROOM | ✅ | `docs/security/LICENSE_MATRIX.md`, `SBOM.md` |
| WORKTREE_CLEAN | ✅ | `git status --porcelain` empty at freeze |
| PRODUCTION_UNTOUCHED | ✅ | zero-egress core; no production endpoint contacted |
| NOMOS_UNTOUCHED | ✅ | HEAD `2cea197e` + dirty=2 + mtime unchanged vs ETAPA-0 |
| HERMES_UNTOUCHED | ✅ | mtime unchanged vs ETAPA-0 |
| OPENCLAW_UNTOUCHED | ✅ | mtime unchanged vs ETAPA-0 |

## Final status (v0.1)

`STATUS_FINAL = EPISTEMOS_V0_1_PASS` — tag `epistemos-v0.1.0`.

---

## EPISTEMOS-02 (SCALE-RETRIEVAL) gates

Adds a rebuildable FTS index to eliminate the v0.1 O(N) search bottleneck while preserving all
v0.1 properties. Detail: [`EPISTEMOS_V0_2_FINAL_REPORT.md`](EPISTEMOS_V0_2_FINAL_REPORT.md).

| Gate | State | Evidence |
|------|-------|----------|
| BASELINE_REGRESSION (all v0.1 gates) | ✅ | 415 v0.1 tests green through IndexedRetriever |
| RETRIEVAL_PROFILE | ✅ | `docs/benchmarks/RETRIEVAL_PROFILE_BASELINE.md` |
| FTS | ✅ | `index/fts.py`; `tests/index/` |
| EXPLAINABLE_FTS | ✅ | `tests/index/test_explainable_fts.py` |
| INDEX_CONSISTENCY | ✅ | `tests/index/test_consistency_rebuild.py`; `verify_index_consistency()` |
| INDEX_REBUILD | ✅ | before==after rebuild; `test_rebuild_reproduces_results` |
| CRASH_RECOVERY (index) | ✅ | `tests/chaos/test_index_chaos.py` |
| RETRIEVAL_SEMANTIC_PARITY | ✅ | `tests/index/test_parity.py` (legacy vs indexed) |
| TEMPORAL_INDEX_QUERY | ✅ | `tests/index/test_temporal_index.py` |
| INDEX_FALLBACK | ✅ | `tests/index/test_fallback.py`; explicit health states |
| VECTOR_OPTIONAL | ✅ | `NullVectorIndex`; core passes with no embeddings |
| FTS_SECURITY | ✅ | `tests/security/test_fts_security.py` |
| INDEX_RACE (30 cycles) | ✅ | `tests/race/test_index_race.py` |
| INDEX_CHAOS | ✅ | `tests/chaos/test_index_chaos.py` |
| MUTATION (index boundaries) | ✅ | 18/18 killed (6 index mutants); `docs/security/MUTATION_REPORT.md` |
| BENCHMARK (legacy vs indexed) | ✅ | `docs/benchmarks/EPISTEMOS_02_FINAL_BENCHMARK.md` |
| ADRS 016–020 | ✅ | `docs/adr/` |

`STATUS_FINAL = EPISTEMOS_V0_2_PASS` — tag `epistemos-v0.2.0` (v0.1.0 unchanged).

---

## EPISTEMOS-03 (AUDIT + CAPABILITY UPLIFT) gates

Adversarial re-audit of v0.2.0, defect fixes, and a measured capability uplift. Detail:
[`EPISTEMOS_V0_3_FINAL_REPORT.md`](EPISTEMOS_V0_3_FINAL_REPORT.md), audit
[`audit/EPISTEMOS_V0_2_AUDIT.md`](audit/EPISTEMOS_V0_2_AUDIT.md).

| Gate | State | Evidence |
|------|-------|----------|
| REBASELINE (cold) | ✅ | v0.2 gates reproduced cold: 616 tests, ruff, mypy, mutation 18/18, benchmark |
| ADVERSARIAL_AUDIT | ✅ | `audit/EPISTEMOS_V0_2_AUDIT.md`; 43 findings verified (108-agent sweep), each material one → red test |
| AUDIT_FINDINGS_RESOLVED | ✅ | 0 material findings open; residuals classified LOW/KNOWN_GAP/FUTURE (documented) |
| A-01 import scope authority | ✅ | `tests/security/test_import_scope.py`; mutant `core_import_scope_authority` |
| A-02 migrate verification | ✅ | `test_import_scope.py`, `test_schema_migration.py` |
| A-11 scoped export | ✅ | `tests/security/test_export_scope.py` |
| A-12 belief closes once | ✅ | `tests/unit/test_belief_close_once.py`; mutants `core_open_belief_guard`, `core_belief_reclose` |
| RETRIEVAL_PARITY (ADR-021) | ✅ | `tests/index/test_fallback_parity.py` — a constraint filters on both paths |
| AGENT/SOURCE ISOLATION | ✅ | `tests/security/test_mutation_guards.py` — confirm delta, merge/split guard, source deref |
| INDEX HEALTH TRUSTWORTHY | ✅ | `tests/index/test_index_robustness.py` — verify content drift, rebuild health, ensure_built |
| BOUNDARY FAIL-CLOSED | ✅ | `tests/security/test_boundary_hardening.py` — REST None, health scope, get oracle, MCP crash |
| TEMPORAL QUERY CONSISTENCY | ✅ | `tests/unit/test_temporal_query_consistency.py` — clock-independent "believed now" |
| PROVENANCE_INDEX (C2) | ✅ | ADR-022; `tests/index/test_provenance_index.py`; explain() 33 800× at 100k, flat |
| UNICODE_SEARCH (C1) | ✅ | ADR-023; `tests/index/test_unicode_tokenizer.py` + fuzz; opt-in, scan/index parity |
| CAPABILITY_CENSUS | ✅ | `roadmap/EPISTEMOS_CAPABILITY_ROADMAP.md` (measurement-driven) |
| SECURITY | ✅ | `tests/security/` incl. 6 new EPISTEMOS-03 files |
| RACE | ✅ | `tests/race/` (30 cycles/scenario) — no regression |
| CHAOS | ✅ | `tests/chaos/` — no regression |
| MUTATION | ✅ | 25/25 killed, 0 survived, 0 invalid (7 new EPISTEMOS-03 boundary mutants) |
| BENCHMARK | ✅ | `benchmarks/EPISTEMOS_03_FINAL_BENCHMARK.md` (before/after; costs disclosed) |
| FULL_REGRESSION (v0.1+v0.2) | ✅ | 700 tests green; ruff + mypy --strict clean |
| DOCS / ADRS (021–023) | ✅ | `docs/adr/`, audit, benchmark, roadmap, `docs/collaboration/` |
| COLLABORATIVE_ARCHITECTURE_ASSESSED | ✅ | `docs/collaboration/COLLABORATIVE_KNOWLEDGE_MODEL.md` (Q1–Q15 + output block) |
| ZERO_EGRESS / NULL_LLM | ✅ | re-verified across the full lifecycle incl. index path |
| WORKTREE_CLEAN | ✅ | `git status --porcelain` empty at freeze |
| NOMOS / HERMES / OPENCLAW UNTOUCHED | ✅ | no EPISTEMOS-caused change vs ETAPA-0 baseline |

`STATUS_FINAL = EPISTEMOS_V0_3_PASS` — tag `epistemos-v0.3.0` (v0.1.0 and v0.2.0 unchanged).

---

## EPISTEMOS-04 (KNOWLEDGE SPACES & CAPABILITY MODEL) gates

Adds a visibility lattice and capability-based authorization so a user can share *selected*
knowledge without exposing the rest. Design: [ADR-024](adr/ADR-024-knowledge-spaces.md),
[ADR-025](adr/ADR-025-capability-authorization.md), [ADR-026](adr/ADR-026-authorized-retrieval.md);
model docs in [`docs/spaces/`](spaces/KNOWLEDGE_SPACE_MODEL.md); report
[`EPISTEMOS_V0_4_FINAL_REPORT.md`](EPISTEMOS_V0_4_FINAL_REPORT.md).

| Gate | State | Evidence |
|------|-------|----------|
| SOURCE_CHECK | ✅ | `import epistemos` → 0.4.0 from repo src |
| BASELINE_REGRESSION (v0.1–v0.3) | ✅ | full suite green; single-agent v0.3 byte-identical |
| NEW_TESTS | ✅ | `tests/spaces/` (8 files) |
| RUFF / MYPY_STRICT | ✅ | `ruff check src tests` clean; `mypy --strict` clean (29 files) |
| KNOWLEDGE_SPACES | ✅ | ADR-024; `test_spaces_model.py` |
| CAPABILITY_ENFORCEMENT | ✅ | ADR-025; `test_capability_model.py`, `test_authz_unit.py` |
| PRIVATE_DEFAULT | ✅ | `spaces == ()` → PRIVATE; `test_spaces_model.py` |
| PRIVATE_TO_PUBLIC_LEAK = 0 | ✅ | `test_private_public_invariant.py` (full adversarial battery) |
| AUTHORIZED_RETRIEVAL | ✅ | ADR-026; candidate-boundary-first; score/count non-leak |
| FTS / GRAPH / PROVENANCE SPACE_ISOLATION | ✅ | `test_space_export_graph.py`, provenance elision |
| EXPORT_IMPORT_SPACE_SAFETY | ✅ | `test_space_export_graph.py` (scoped export, crafted import) |
| TENANT_ISOLATION | ✅ | unchanged from v0.3 + `test_authz_unit.py` |
| LEDGER_INTEGRITY / PROJECTION_REBUILD / INDEX_REBUILD | ✅ | freeze proofs; `test_space_chaos.py` |
| RACE (30 cycles) | ✅ | `test_space_race.py` (share vs revoke, concurrent grants) |
| CHAOS | ✅ | `test_space_chaos.py` (recovery, index corruption, promotion) |
| MUTATION_NON_EQUIVALENT_SURVIVED = 0 | ✅ | 32/32 killed (7 new spaces boundary mutants) |
| PERFORMANCE | ✅ | `benchmarks/EPISTEMOS_04_AUTHZ_BENCHMARK.md` (overhead disclosed) |
| BACKWARD_COMPATIBILITY | ✅ | `test_backward_compat.py` (legacy → PRIVATE, never PUBLIC) |
| ZERO_EGRESS / LOCAL_FIRST | ✅ | freeze proof (0 socket ops full lifecycle incl. spaces) |
| MIT_LICENSE_MIGRATION | ✅ | ADR-027; LICENSE/pyproject/docs = MIT; APACHE_REFERENCE_RESIDUAL=0 |
| DOCS / ADRS (024–027) | ✅ | `docs/adr/`, `docs/spaces/`, benchmark, report |
| WORKTREE_CLEAN | ✅ | empty at freeze |
| NOMOS / HERMES / OPENCLAW UNTOUCHED | ✅ | no EPISTEMOS-caused change vs baseline |

`STATUS_FINAL = EPISTEMOS_V0_4_PASS` — tag `epistemos-v0.4.0` (v0.1.0/v0.2.0/v0.3.0 unchanged).

## EPISTEMOS-05 (COLLABORATIVE CLAIMS) gates

Adds verifiable collaborative epistemology on the v0.4 spaces: **contribution ≠ truth**. Claim /
evidence / review are first-class; belief is *derived*; acceptance is *governed* via a policy port.
Design: [ADR-028](adr/ADR-028-collaborative-claims.md),
[ADR-029](adr/ADR-029-derived-belief-governed-acceptance.md); model docs in
[`docs/claims/`](claims/CLAIM_MODEL.md); report
[`EPISTEMOS_V0_5_FINAL_REPORT.md`](EPISTEMOS_V0_5_FINAL_REPORT.md).

| Gate | State | Evidence |
|------|-------|----------|
| SOURCE_CHECK | ✅ | `import epistemos` → 0.5.0 from repo src |
| BASELINE_REGRESSION (v0.1–v0.4) | ✅ | full suite 855 green; single-agent behaviour unchanged |
| NEW_TESTS | ✅ | `tests/claims/` (7 files: model, pipeline, firewall, adversarial, race, chaos) |
| RUFF / MYPY_STRICT | ✅ | `ruff check src tests` clean; `mypy --strict` clean (32 files) |
| CONTRIBUTION_NOT_TRUTH | ✅ | bare claim = PROPOSED; self-confirm only SUPPORTED; `test_adversarial.py` |
| CLAIM / EVIDENCE / REVIEW model | ✅ | ADR-028; `test_claim_model.py`, `test_claim_pipeline.py` |
| DERIVED_BELIEF (never stored) | ✅ | ADR-029; `claims/belief.py`; `test_claim_model.py` |
| MAJORITY_IS_NOT_TRUTH | ✅ | one dispute ⟶ DISPUTED; `test_multiple_reviewers_disagree…` |
| GOVERNED_ACCEPTANCE (policy port) | ✅ | `knowledge.accept` non-default; `LocalDefaultPolicy`; engine gate before policy |
| SELF_ACCEPTANCE_DENIED | ✅ | §32; `test_claimant…cannot_self_accept` |
| CLAIM_SPACE_LEAK = 0 | ✅ | `test_claim_firewall.py` |
| EVIDENCE_SPACE_LEAK = 0 | ✅ | `test_claim_firewall.py` |
| REVIEW_SPACE_LEAK = 0 | ✅ | reviews inherit claim spaces; `test_claim_firewall.py` |
| PRIVATE_TO_PUBLIC_LEAK = 0 (composition §15) | ✅ | public claim never exposes private evidence; `test_public_claim…` |
| EXPLAIN_AUTHZ_BEFORE_TRAVERSAL | ✅ | `explain_claim`; v0.4 explain leak stays closed |
| NO_EXISTENCE_ORACLE | ✅ | `test_no_existence_oracle_across_the_space_boundary` |
| BITEMPORAL_CLAIMS | ✅ | `test_claim_is_bitemporal` |
| LEDGER_INTEGRITY / PROJECTION_REBUILD | ✅ | `test_rebuild_projection_equals_replay_with_claims`, chaos |
| RACE (30 cycles) | ✅ | `test_claim_race.py` (reviews vs read; grant toggle vs read) |
| CHAOS | ✅ | `test_claim_chaos.py` (rebuild-from-ledger; no partial acceptance; no leak) |
| MUTATION_NON_EQUIVALENT_SURVIVED = 0 | ✅ | 39/39 killed (7 new claim boundary mutants); `MUTATION_REPORT.md` |
| PERFORMANCE (no core regression) | ✅ | `benchmarks/bench.py`; claim create/belief/explain reported |
| ZERO_EGRESS / LOCAL_FIRST / NULL_LLM | ✅ | policy port is offline; 0 socket ops full claim lifecycle |
| MIT_LICENSE (unchanged) | ✅ | LICENSE=MIT; APACHE_REFERENCE_RESIDUAL=0 |
| DOCS / ADRS (028–029) | ✅ | `docs/adr/`, `docs/claims/` (8 files), report |
| WORKTREE_CLEAN | ✅ | empty at freeze |
| NOMOS / HERMES / OPENCLAW UNTOUCHED | ✅ | policy port is a *plug*, not a dependency; no change vs baseline |

`STATUS_FINAL = EPISTEMOS_V0_5_PASS` — tag `epistemos-v0.5.0` (v0.1.0–v0.4.0 unchanged).

## v0.6.0 — Context Envelope (EPISTEMOS-08)

Compress the *transmission* of memory, not the memory. A post-retrieval, evidence-preserving
transform (`engine.context`) promoting only what EPISTEMOS-07 proved; Dimensions/Resonance/
Microconnections/Contextual Geometry stay rejected (EPISTEMOS-06). ADR-033…037.

| Gate | Status | Evidence |
|---|---|---|
| CRITICAL_EVIDENCE_LOSS = 0 | ✅ | `tools/eps08_benchmark.py` (1000+ state changes) |
| CONTRADICTION_LOSS = 0 | ✅ | pinning incl. attached, re-authorized; ADR-035 |
| TEMPORAL_REGRESSION = 0 | ✅ | history preserved for non-current intents; ADR-034 |
| ANSWER_CORRECTNESS_DELTA ≥ 0 | ✅ | +0.0 (100% → 100%) at scale |
| TOKEN_REDUCTION > 0 | ✅ | +34.6% (up to ~35% in measured redundant scenarios; not universal) |
| SCALE (stable, no decay) | ✅ | +35% at 100/500/2000 entities (709→14009 events); latency linear |
| PRIVATE_CONTEXT_LEAK = 0 | ✅ | `tests/context/test_context.py`; cross-tenant/space; benchmark-scale sweep |
| RACE (30×) | ✅ | 6 threads × 30 concurrent builds, two principals; no error/cross-contamination |
| CHAOS (reproducible) | ✅ | same store → byte-identical envelope 5×; structural reproducibility across rebuilds |
| MUTATION_NON_EQUIVALENT_SURVIVED = 0 | ✅ | 6/6 killed (pin, history, attached-authz, provenance, incomplete, dup/corroboration); `tools/eps08_mutation.py` |
| EXPERIMENTAL OFF BY DEFAULT | ✅ | budget-pack + continuation gated in `EnvelopeConfig`; ADR-037 |
| FULL REGRESSION | ✅ | **946 passed**, ruff + mypy `--strict` clean |
| DOCS / ADRS (033–037) | ✅ | `docs/context/` (7 files), `docs/adr/` |
| NOMOS / HERMES / OPENCLAW UNTOUCHED | ✅ | additive module; no cross-project change |

`STATUS_FINAL = EPISTEMOS_V0_6_PASS` — tag `epistemos-v0.6.0` (v0.1.0–v0.5.0 unchanged).

## v0.7.0 — EPCTX Protocol (EPISTEMOS-09)

Turn EPCTX/1 into a stable, provider-agnostic consumption contract with SDK/REST/MCP surfaces and a
generic agent harness, without coupling the core to any consumer. ADR-038…044.

| Gate | Status | Evidence |
|---|---|---|
| EPCTX_SPEC / SERIALIZATION / VERSIONING | ✅ | `docs/protocol/*`; `tests/protocol/test_protocol.py` |
| DETERMINISTIC_SERIALIZATION | ✅ | canonical JSON; same logical → same bytes; integrity self-consistent |
| GENERIC_SDK / REST_CONTEXT / MCP_CONTEXT | ✅ | `sdk.py`, `POST /context`, `epistemos_context`; parity test |
| TRANSPORT_PARITY (local == REST == MCP) | ✅ | `test_local_rest_mcp_equivalent`, `test_expansion_parity…` |
| GENERIC_AGENT_HARNESS | ✅ | `GenericAgentHarness` over the client; null/fake offline models |
| CLAIM_TYPE_PRESERVED | ✅ | `object_type` + `belief_state`/`accepted_state`; claim never a fact |
| CONTRADICTIONS_PRESERVED | ✅ | separate `contradictions` section + `disputed` flag |
| CONTEXT_INCOMPLETE_PRESERVED | ✅ | `completeness{complete,reasons}` in the wire (ADR-040) |
| TEMPORAL_STATE_PRESERVED | ✅ | per-object valid/tx time + `is_current`; doc has_current/has_historical |
| PROVENANCE_PRESERVED | ✅ | per-object source/derived_from/evidence_refs; queryable table |
| PRIVATE_EPCTX_LEAK = 0 | ✅ | `tests/protocol/test_protocol_security.py` |
| PRIVATE_EXPANSION_LEAK = 0 | ✅ | forged/cross-principal/cross-tenant/revoked handles refused |
| CROSS_TENANT_EPCTX_LEAK = 0 | ✅ | outsider document empty; REST/MCP identity server-side |
| PROMPT_INJECTION_DATA_ONLY | ✅ | renderer fences evidence; `test_prompt_injection…stays_data` |
| RACE (30×) | ✅ | `test_protocol_race_chaos.py`: context vs mutation, two-principal, expansion vs revoke |
| CHAOS | ✅ | rebuild reproduces shape; expand against shrunken store = honest partial |
| MUTATION NON_EQUIVALENT_SURVIVED = 0 | ✅ | 7/7 killed; `tools/eps09_mutation.py` |
| AGENT_BENCH | ✅ | `tools/eps09_agent_bench.py`: EPCTX makes dispute/temporal/provenance available (raw does not) |
| BACKWARD_COMPAT | ✅ | `engine.search` + `engine.context` unchanged; EPCTX additive |
| FULL REGRESSION | ✅ | **996 passed**; ruff + mypy `--strict` clean |
| DOCS / ADRS (038–044) | ✅ | `docs/protocol/` (10), `docs/integrations/` (4), `docs/adr/` |
| ZERO_EGRESS / LOCAL_FIRST / MIT | ✅ | stdlib-only transports; localhost REST; MIT |
| NOMOS / HERMES / OPENCLAW UNTOUCHED | ✅ | spec-only integration notes; no core dependency, no import |

`STATUS_FINAL = EPISTEMOS_V0_7_PASS` — tag `epistemos-v0.7.0` (v0.1.0–v0.6.0 unchanged).
