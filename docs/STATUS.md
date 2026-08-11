# EPISTEMOS — Gate Matrix & Evidence Ledger

This file is the single honest source of truth for the V0.1 gates (mission §40).
A gate is **PASS** only with specific, reproducible evidence — never because "the
suite is green" (mission §41). `PARTIAL` is never reported as `PASS`.

Legend: ✅ PASS · 🟡 PARTIAL · ⛔ BLOCKED · ⬜ PENDING

| Gate | State | Evidence |
|------|-------|----------|
| ETAPA0_ISOLATION | ✅ | `docs/architecture/ETAPA0_ISOLATION.md`; baseline HEADs/mtimes captured; all writes under `~/Projects/epistemos` |
| NAMING | ⬜ | `docs/research/NAMING_REPORT.md` (pending census workflow) |
| CENSUS | ⬜ | `docs/research/COMPETITOR_MATRIX.md` |
| FEATURE_HARVEST | ⬜ | `docs/research/FEATURE_HARVEST.md` |
| CORE_MODEL | ⬜ | `docs/spec/CORE_MODEL.md` + `tests/unit/test_model.py` |
| TEMPORAL | ⬜ | bitemporal valid/tx time; `tests/unit/test_temporal.py` |
| PROVENANCE | ⬜ | `explain(fact)` genealogy; `tests/unit/test_provenance.py` |
| CONTRADICTION | ⬜ | assert/supersede/retract/contradict; `tests/unit/test_contradiction.py` |
| MEMORY | ⬜ | working/episodic/semantic/procedural/session taxonomy; `tests/unit/test_memory.py` |
| GRAPH | ⬜ | entities/relations/traversal; `tests/unit/test_graph.py` |
| RETRIEVAL | ⬜ | explainable hybrid retrieval; `tests/unit/test_retrieval.py` |
| TENANT_ISOLATION | ⬜ | fail-closed cross-tenant; `tests/security/test_tenant_isolation.py` |
| AGENT_ISOLATION | ⬜ | fail-closed cross-agent; `tests/security/test_agent_isolation.py` |
| ZERO_EGRESS_DEFAULT | ⬜ | socket guard test; `tests/security/test_zero_egress.py` |
| NULL_LLM_MODE | ⬜ | full core works with `NullModelProvider` |
| CRASH_RECOVERY | ⬜ | kill-during-write integrity; `tests/chaos/` |
| BACKUP_RESTORE | ⬜ | populate→snapshot→reset→restore→compare |
| EXPORT_IMPORT | ⬜ | versioned round-trip; `tests/unit/test_export.py` |
| SECURITY_BATTERY | ⬜ | S1–S40 mapped in `docs/security/THREAT_MODEL.md` |
| RACE | ⬜ | deterministic multi-writer battery; `tests/race/` |
| MUTATION_CRITICAL | ⬜ | NON_EQUIVALENT_SURVIVED=0 on critical boundaries |
| BENCHMARK | ⬜ | reproducible; `docs/benchmarks/RESULTS.md` |
| DOCS | ⬜ | ADR-001…015 + research + spec + security |
| WORKTREE_CLEAN | ⬜ | `git status` clean at freeze |
| PRODUCTION_UNTOUCHED | ✅ | no production system contacted; core is zero-egress |
| NOMOS_UNTOUCHED | ✅ (interim) | baseline HEAD `2cea197e`; re-verify at freeze |
| HERMES_UNTOUCHED | ✅ (interim) | baseline mtime captured; re-verify at freeze |
| OPENCLAW_UNTOUCHED | ✅ (interim) | baseline mtime captured; re-verify at freeze |

## Final status

`STATUS_FINAL = <pending>` — one of `EPISTEMOS_V0_1_PASS` or `EPISTEMOS_V0_1_BLOCKED`.
