# EPISTEMOS v0.2 — Final Report (SCALE-RETRIEVAL)

Mission **EPISTEMOS-02**. Eliminate the v0.1 O(N) retrieval bottleneck with a rebuildable,
tenant/temporal-aware, explainable, secure FTS index — preserving every v0.1 property and gate.
No integration with NOMOS/Hermes/OpenClaw (still forbidden); the v0.1.0 tag is untouched.

## Headline result

Lexical search latency (selective query), legacy O(N) scan → indexed FTS5:

| scale | LEGACY p50 | INDEXED p50 | speedup |
|------:|-----------:|------------:|--------:|
| 1,000 | 69.6 ms | **0.28 ms** | 247× |
| 10,000 | 620 ms | **2.4 ms** | 259× |
| 100,000 | **6,199 ms** | **33.9 ms** | 183× |

The multi-second bottleneck is gone: 100k search drops from 6.2 s to 34 ms (broad "matches-all"
query: 173 ms). Write latency stays flat at ~0.44 ms (v0.1 no-index baseline ~0.42 ms — small,
scale-independent amplification). Full data: `docs/benchmarks/EPISTEMOS_02_FINAL_BENCHMARK.md`.

## Summary

```
REPO                 = ~/Projects/epistemos
BRANCH               = feat/epistemos-02-scale-retrieval
BASELINE_TAG         = epistemos-v0.1.0 (c0faabf) — INTACT, unchanged
HEAD                 = <the commit tag epistemos-v0.2.0 points to>
TAG                  = epistemos-v0.2.0 (annotated)
PYTHON               = 3.14.5 (runtime target >=3.11)
SOURCE_CHECK         = PASS

TESTS_PASSED         = 616 (unit 120 · security 72 · race 360 · chaos 14 · integration 18 · index 32)
TESTS_FAILED         = 0
RUFF                 = PASS
MYPY (--strict)      = PASS
MUTATION             = PASS (18/18 non-equivalent killed, 0 survived; +6 index-boundary mutants)

BASELINE_REGRESSION  = PASS (all 415 v0.1 tests green through IndexedRetriever)
FTS                  = PASS      EXPLAINABLE_FTS      = PASS
INDEX_CONSISTENCY    = PASS      INDEX_REBUILD        = PASS
CRASH_RECOVERY       = PASS      RETRIEVAL_SEMANTIC_PARITY = PASS
TEMPORAL_INDEX_QUERY = PASS      INDEX_FALLBACK       = PASS
TENANT_ISOLATION     = PASS      ZERO_EGRESS          = PASS
NULL_LLM             = PASS      VECTOR_OPTIONAL      = PASS
SECURITY (FTS)       = PASS      RACE (30 cycles)     = PASS
CHAOS                = PASS      BENCHMARK            = PASS
ADRS 016-020         = PASS      DOCS                 = PASS

WORKTREE_CLEAN       = TRUE
NOMOS_UNTOUCHED      = TRUE   (HEAD 2cea197e + dirty=2 + mtime unchanged)
HERMES_UNTOUCHED     = TRUE   (mtime unchanged)
OPENCLAW_UNTOUCHED   = TRUE   (mtime unchanged)
PRODUCTION_UNTOUCHED = TRUE

STATUS_FINAL         = EPISTEMOS_V0_2_PASS
```

## What changed (design)

- **`epistemos/index/`** — a substitutable index layer. `LexicalIndex` port + `IndexHealth` states;
  `SqliteFtsIndex` (FTS5) lives in the store's own connection so index updates are **transactionally
  consistent** with the projection; `VectorIndex`/`HybridScoring` are design-only ports (vector stays
  optional, no model, no egress). ADR-016/017/018/020.
- **Safe query** — user text is normalized to quoted literal tokens (capped), so FTS5/SQL operators
  in a query are inert data (no injection, no wildcard/deep-boolean explosion). ADR-017.
- **Retriever** — `LegacyScanRetriever` (v0.1 reference/fallback) and `IndexedRetriever` share all
  scoring; the FTS path returns candidates in O(matches) and re-ranks with the same explainable
  components (`lexical`/`exact`/`temporal`/`authority`/`recency`, `why_returned`).
- **Engine** — `_persist` routes every projection write through the index atomically and **isolates
  any index error** so a broken index can never block a core write; `search` uses the index only when
  `HEALTHY`, else falls back to the correct scan (never stale/incomplete), reporting the method used;
  `health()` exposes index state; `verify_index_consistency()` / `rebuild_index()`. ADR-019.

## Per-gate evidence

| Gate | Evidence / command |
|------|--------------------|
| RETRIEVAL_PROFILE | `python tools/profile_retrieval.py` → `docs/benchmarks/RETRIEVAL_PROFILE_BASELINE.md` |
| BASELINE_REGRESSION | 415 v0.1 tests green (retrieval now via IndexedRetriever on SQLite) |
| EXPLAINABLE_FTS | `tests/index/test_explainable_fts.py` (fts5-bm25 method + full components) |
| INDEX_CONSISTENCY | `tests/index/test_consistency_rebuild.py`; `verify_index_consistency()` after every op |
| INDEX_REBUILD | before==after rebuild (`test_rebuild_reproduces_results`, incl. `rebuild_projection`) |
| RETRIEVAL_SEMANTIC_PARITY | `tests/index/test_parity.py` (legacy vs indexed; differences ADR-017) |
| TEMPORAL_INDEX_QUERY | `tests/index/test_temporal_index.py` (current/as_of valid/as_of tx) |
| INDEX_FALLBACK | `tests/index/test_fallback.py` (health states; degraded → scan; memory→scan) |
| VECTOR_OPTIONAL | `NullVectorIndex`; core passes with no embeddings (whole suite) |
| FTS_SECURITY | `tests/security/test_fts_security.py` (10 hostile queries inert; no tenant bypass) |
| RACE | `tests/race/test_index_race.py` (write/supersede/rebuild/backup/2-tenant × 30) |
| CHAOS | `tests/chaos/test_index_chaos.py` (SIGKILL, delete/corrupt index, index-fail-doesn't-block) |
| MUTATION | `python tools/mutation_harness.py` → 18/18 killed (6 index mutants) |
| BENCHMARK | `python benchmarks/compare_retrieval.py` → `EPISTEMOS_02_FINAL_BENCHMARK.md` |

## Semantic parity — documented intentional differences (ADR-017)

Legacy and indexed retrievers agree on the text-matching result set, temporal validity, tenant/agent
isolation, source-trust behavior, contradiction behavior, and explanation structure (parity tests).
Intentional, ADR-approved differences: (1) the `lexical` score is BM25 (FTS5) vs v0.1 TF·IDF, so fine
ordering among purely-lexical ties differs; (2) for text queries the indexed path returns only
term-matching objects (standard search semantics) whereas the v0.1 scan also surfaced non-matching
recency hits; (3) recall for a single query is bounded by `CANDIDATE_POOL` (500) for very
high-frequency terms.

## Known limitations (disclosed)

1. **Unicode search** — the index (and v0.1 tokenizer) use ASCII tokenization; non-ASCII content is
   not tokenized as searchable terms (unchanged from v0.1). A unicode tokenizer is a future option.
2. **Recall pool** — very high-frequency terms re-rank only the top `CANDIDATE_POOL` BM25 candidates
   (documented perf/recall trade-off; raise the pool if a measured workload needs it).
3. **Vector/graph retrieval** — designed (ADR-020, ports present) but not implemented in v0.2; vector
   stays optional and off by default.

## Reproduce

```bash
cd ~/Projects/epistemos && . .venv/bin/activate && uv pip install -e ".[dev]"
python -m pytest tests/unit tests/security tests/race tests/chaos tests/integration tests/index  # 616
ruff check src tests && mypy src/epistemos                                                        # clean
python tools/mutation_harness.py                                                                  # 18/18
python benchmarks/compare_retrieval.py --scales 1000 10000 100000                                 # legacy vs indexed
```

**STATUS_FINAL = EPISTEMOS_V0_2_PASS**
