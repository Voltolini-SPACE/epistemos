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
