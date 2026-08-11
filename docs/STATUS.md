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

## Final status

`STATUS_FINAL = EPISTEMOS_V0_1_PASS` — tag `epistemos-v0.1.0`.
