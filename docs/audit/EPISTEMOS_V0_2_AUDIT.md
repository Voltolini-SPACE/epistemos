# EPISTEMOS v0.2.0 — Adversarial Audit (EPISTEMOS-03)

**Baseline audited:** tag `epistemos-v0.2.0` (`0451301`).
**Method:** every claim in the README, ADRs, STATUS and final reports was treated as a *claim*
until re-proven by an executed probe. Findings came from (a) direct probing of the invariants and
(b) a 6-dimension adversarial sweep (108 agents: attack → refute → impact-judge), each finding
verified by an independent skeptic and an independent impact judge. 43 findings survived
verification; 8 were rejected as not-real. Rejected and negative results are recorded at the end so
this document reflects what held up as well as what broke.

**Classification** (per the owner addendum §31): `CURRENT_DEFECT` and materially-necessary
`CURRENT_HARDENING` are the only classes that may block the freeze. `FOUNDATIONAL_PRIMITIVE` and
`FUTURE_CAPABILITY` go to the roadmap. `OVERCLAIM` is corrected in docs.

Every finding marked **FIXED** below has a red-then-green test named in the "Resolution" column and
a mutant in `tools/mutation_harness.py` where the boundary is critical.

---

## CRITICAL

| ID | Claim vs reality | Class | Resolution |
|----|------------------|-------|------------|
| A-01 | ADR-010 "fail-closed multi-tenant". Reality: the projection trusted `payload["tenant"]`/`["namespace"]` (attacker-controlled on import), so a hand-built export with an internally-valid hash chain wrote objects into **any** tenant's scope. | CURRENT_DEFECT | **FIXED** — `_apply` takes scope from the sealed record header; payload/ref scope mismatch → `IntegrityError`. `test_import_scope.py`; mutant `core_import_scope_authority`. |
| A-02 | Import is tamper-evident. Reality: `import_events(migrate=True)` re-sealed the incoming events **without verifying the chain**, silently disabling tamper-evidence. | CURRENT_DEFECT | **FIXED** — the incoming chain is verified as received, before migration reshapes payloads; a chainless export is refused under `verify=True`. `test_import_scope.py`, `test_schema_migration.py`. |
| A-11 / B-08(b) | `Engine.export()` took no principal and dumped the **whole multi-tenant ledger**; REST `GET /export` served it to any authenticated token. | CURRENT_DEFECT | **FIXED** — `export(principal)` is scope-limited and re-sealed into a fresh valid chain; `scope="all"` needs `admin`; REST/SDK pass the caller's principal. `test_export_scope.py`. |
| A-12 / T-01 | ADR-003 "transaction time never moves". Reality: `supersede`/`retract`/`correct_validity` on an **already-closed** belief overwrote `tx_to`, so `as_of(at_tx=T)` changed its answer about a past instant; double-`retract` even *resurrected* a withdrawn belief. Invisible to `verify_integrity`, survived `rebuild_projection`. | CURRENT_DEFECT | **FIXED** — command layer refuses to re-close (`_open_belief` → `ConflictError`); projection keeps the earliest close, so even a legacy/crafted ledger rebuilds to the correct history. `test_belief_close_once.py`; mutants `core_open_belief_guard`, `core_belief_reclose`. |
| B-01 (boundaries) | An `AuthResolver` returning `None` (not raising) reached the Engine as `principal=None`, and `export(None)` is the unscoped dump — a resolver bug leaked every tenant. | CURRENT_DEFECT | **FIXED** — REST fails closed if auth does not resolve a real `Principal`. `test_boundary_hardening.py`; mutant `rest_none_principal`. |

## HIGH

| ID | Claim vs reality | Class | Resolution |
|----|------------------|-------|------------|
| A-03 / A-04 | ADR-019 fallback "never returns stale/incomplete". Reality: a no-match text query returned **every object** via the scan but 0 via the index; a structural filter over non-fact `kinds` returned the object via the scan but 0 via the index. A degraded index silently changed "find what matches" into "list the namespace". | CURRENT_DEFECT | **FIXED** — one shared predicate: text requires a lexical hit, structural constraints filter, on both paths. ADR-021. `test_fallback_parity.py`. |
| B-03 (isolation) | `confirm()` accepted a **negative** delta, so any agent could zero a rival's fact confidence and flip which fact is "current". | CURRENT_DEFECT | **FIXED** — `confirm` rejects `delta < 0` (corroboration only). `test_mutation_guards.py`; mutant `core_confirm_negative_delta`. |
| B-04 (isolation) | `merge_entities`/`split_entity` rewrote another agent's entity **in place** with no owner guard (unlike supersede/retract). | CURRENT_DEFECT | **FIXED** — both carry `guard_owner`; admin overrides. `test_mutation_guards.py`. |
| B-06 (isolation) | `search()`/`explain()`/both trust lookups dereferenced a fact's `source` pointer with **no scope check** → cross-tenant URI/trust disclosure. | CURRENT_DEFECT | **FIXED** — all four sites require the source to share the object's scope. `test_mutation_guards.py`; mutant `retrieval_source_scope`. |
| B-01 / OV-02 / LT-01 (index) | FTS content-cell corruption (row intact) was **invisible to `verify()`/`health()`**: index stayed HEALTHY and search returned wrong/incomplete results, surviving reopen. | CURRENT_DEFECT | **FIXED** — `verify()` compares each row's indexed content to the object's text; drift → DEGRADED → scan fallback. `test_index_robustness.py`; mutant `idx_verify_content_drift`. |
| B-03 (index) | `MAX_QUERY_TERMS` bounded only the FTS path; the scan fallback fed the full uncapped token list into TF·IDF (query-cost DoS). | CURRENT_HARDENING | **FIXED** — both paths cap via `_query_terms` (also dedups → tighter parity). `test_index_robustness.py`. |
| B-02 (boundaries/isolation) | REST `X-Eps-Namespace` lets any token read/write any namespace in its tenant; "agent-private memory via namespace" is thereby only tenant-deep. | OVERCLAIM → FOUNDATIONAL | **DOCUMENTED** — namespace is a partition **within** the tenant isolation boundary, not a per-agent authorization boundary. True per-agent/space access control is EPISTEMOS-04 (Knowledge Spaces + capability model). ADR-008 corrected; see `docs/collaboration/`. |
| B-03 (boundaries) | A client-controlled argument of the wrong type (`confidence="abc"`) raised an uncaught `ValueError` that **killed `serve_stdio`**. | CURRENT_DEFECT | **FIXED** — MCP maps `ValueError`/`TypeError` to a tool error and keeps serving. `test_boundary_hardening.py`. |
| B-04 (boundaries) | REST `/facts` silently dropped `derived_from` and `memory_class`, severing provenance links created over REST. | CURRENT_DEFECT | **FIXED** — both are forwarded. `test_misc_hardening.py`. |
| T-02 | The repo's own race test asserted "one wins, the other raises (belief already closed)" — but neither raised (the guard did not exist). | CURRENT_DEFECT | **FIXED** as a consequence of A-12: re-closing now raises `ConflictError`; the concurrent case is covered. |
| T-03 | `confirm()` mutates a fact's confidence **in place** (no new generation), so a later confirmation retroactively changes the winner of a past `as_of()`. | FUTURE_CAPABILITY | **DOCUMENTED** — confidence is a mutable annotation, not a bitemporally-versioned quantity; the `delta≥0` fix removes the weaponization. Generational confidence is EPISTEMOS-05. ADR-003 note added. |
| OV-01 | The README's flagship bitemporal example was wrong: `as_of("2026-01-15") -> "X"` returned `None` because it used `supersede(object=None)` (closes belief) where it needed `end_fact` (ends validity, keeps the value). | OVERCLAIM | **FIXED** — README uses `end_fact`; `test_readme_example.py` pins the outputs. |
| OV-03 | A transient "database is locked" at open was caught by the same handler as "no FTS5" and **permanently** marked the index UNAVAILABLE. | CURRENT_DEFECT | **FIXED** — only a genuinely absent FTS5 module yields UNAVAILABLE; other errors propagate. `test_misc_hardening.py`. |

## MEDIUM

| ID | Claim vs reality | Class | Resolution |
|----|------------------|-------|------------|
| B-06 / B-07 (boundaries/isolation) | `health(principal)` returned store-**global** `event_count` and `head_hash` — a cross-tenant write-activity oracle. | CURRENT_DEFECT | **FIXED** — a scoped caller sees only its scope's count and no global head; operator (no principal) keeps the global view. `test_boundary_hardening.py`. |
| B-01 (isolation) | `Engine.get()` returned `None` for absent but raised `NotFoundError` for cross-scope — an existence oracle. | CURRENT_HARDENING | **FIXED** — `get()` returns `None` for both; `explain()` raises for both. `test_boundary_hardening.py`. |
| B-05 (boundaries) | The REST handler never drained an unconsumed body on error paths → HTTP request smuggling on a pipelined connection. | CURRENT_DEFECT | **FIXED** — error paths drain the body. `test_misc_hardening2.py`. |
| B-06 (isolation) | The 64 KiB metadata cap was enforced only on create; cross-agent `confirm`/`contradict` appended without re-check → unbounded growth. | CURRENT_HARDENING | **FIXED** — projected annotation lists bounded to the most recent 256 (full history stays in the ledger). `test_misc_hardening2.py`. |
| B-05 (index) | `kinds` accepted a bare `str` (per-character) or a non-`str` element, interpreted incompatibly by the two retrievers. | CURRENT_HARDENING | **FIXED** — `kinds` must be a tuple/list of strings. `test_misc_hardening.py`. |
| B-06 (index) | A single `observe(text="")` defeated `ensure_built`'s count heuristic → full index rebuild on **every** open. | CURRENT_HARDENING | **FIXED** — falls back to a precise searchable-set comparison only when the cheap check disagrees. `test_index_robustness.py`. |
| T-04 | `supersede` without an explicit `valid_from` defaults the replacement's `valid_from` to the transaction instant, leaving a validity hole. | FUTURE_CAPABILITY | **DOCUMENTED** — documented default; `end_fact`/`correct_validity` are the tools for boundary-preserving edits (see README). |
| T-05 | `current()` anchored the valid axis on the injected clock but the transaction axis on wall-clock. | CURRENT_DEFECT | **FIXED** — "believed now" is the open-interval test (`tx_to is None`), clock-independent. `test_temporal_query_consistency.py`. |
| T-06 | `search(at_tx=T, believed_only=True)` filtered on "believed now", ignoring `at_tx`. | CURRENT_DEFECT | **FIXED** — `believed_only` honours `at_tx`. `test_temporal_query_consistency.py`. |
| LT-02 | `health(verify=True)` could report `state=INDEX_HEALTHY` together with `consistent=False`. | CURRENT_DEFECT | **FIXED** — verify runs before the state is read. `test_index_robustness.py`. |
| LT-04 | `MemoryStore` vs `SQLiteStore` iteration order diverges, so `recall(limit=n)` could return different objects on ties. | CURRENT_HARDENING | **FIXED (defensively)** — verified deterministic across backends with distinct timestamps; cross-backend test added. `test_misc_hardening.py`. |
| LT-05 | `SQLiteStore.backup()` hangs forever when called inside the store's own transaction. | CURRENT_DEFECT | **FIXED** — fails fast with `StorageError`. `test_misc_hardening2.py`. |
| LT-07 | `rebuild_projection()` rebuilt the index but never reset a DEGRADED index to HEALTHY → search stuck on the O(N) scan forever. | CURRENT_DEFECT | **FIXED** — `restore_healthy()` after a verified rebuild. `test_index_robustness.py`. |
| LT-03 | SQL type affinity makes `facts()`/`current()` match non-string query values on SQLite only. | KNOWN_GAP | **DOCUMENTED** — not reachable through the Engine (which validates query values to `str`); a store-conformance note, EPISTEMOS-04 hardens the port contract. |
| OV-04 / B-07 (index) | Indexed search is O(matches across **all** tenants): a shared FTS table with a post-`MATCH` tenant filter, so a neighbour tenant's corpus inflates your latency. | FOUNDATIONAL | **DOCUMENTED** — a real architectural property (not a leak; the tenant filter is correct). Per-space index partitioning is EPISTEMOS-04. Roadmap. |
| OV-05 / OV-06 | `docs/benchmarks/RESULTS.md` numbers drifted from HEAD; write amplification understated (~1.05× claimed vs 1.34–1.62× p50 measured). | OVERCLAIM | **CORRECTED** — `docs/benchmarks/EPISTEMOS_03_FINAL_BENCHMARK.md` re-measures on HEAD with honest write-amplification and DB-size numbers. |

## LOW

| ID | Summary | Class | Resolution |
|----|---------|-------|------------|
| T-07 | `timeline()` sorted validity lexicographically over ISO strings (mixed offsets mis-ordered). | CURRENT_HARDENING | **FIXED** — sorts by parsed instants. `test_misc_hardening2.py`. |
| T-08 | `instant_in_interval()` (public) raised `TypeError` on a naive datetime while `valid_at`/`believed_at` accept one. | CURRENT_HARDENING | **FIXED** — treats naive as UTC. `test_misc_hardening2.py`. |
| B-07 (boundaries) | Missing params / bad `Content-Length` map to HTTP 500 echoing the Python exception text. | KNOWN_GAP | **PARTIAL** — the smuggling half (B-05) is fixed; precise 400-mapping of every missing-field case is deferred (cosmetic, no isolation impact). |
| B-08 (boundaries) | `search(limit=-1)` sliced all-but-one instead of erroring. | CURRENT_HARDENING | **FIXED** — negative/non-int limit rejected. `test_misc_hardening.py`. |
| OV-07 | THREAT_MODEL S31 cites `PRAGMA integrity_check` as shipped; it appears nowhere. | OVERCLAIM | **CORRECTED** — S31 text updated to describe the hash-chain verification actually shipped. |
| OV-08 | Package identified as `0.1.0` while docs declared v0.2 frozen. | OVERCLAIM | **FIXED** — bumped to `0.3.0`. |
| B-04 (index) | `MAX_QUERY_TERMS` truncates to the first 64 distinct tokens (undocumented). | OVERCLAIM | **DOCUMENTED** — now applied identically on both paths and noted in ADR-017/021. |

---

## Rejected findings (probed, did NOT hold as real defects)

The verification pass rejected 8 candidate findings. Notable ones re-checked directly:

- **kinds degrades the shared index** (claimed process-wide DoS): a non-string `kind` did **not**
  degrade the index in practice (SQLite coerced it harmlessly); nonetheless `kinds` is now validated
  (B-05) as defense-in-depth.
- **scan query DoS at 50k terms**: measured ~25 ms on a small corpus — bounded, not the claimed
  runaway; the `MAX_QUERY_TERMS` cap (B-03) is applied anyway.
- **LT-09 `LedgerRecord.meta` outside `entry_hash`**: `meta` is unused by the shipped write path;
  no live path populates it, so it is not a tamper vector today (noted for the port contract).
- **B-09 ADR-011 provider wiring "does not exist"**: `NullModelProvider` exists and the core runs
  with no model (zero-egress + null-LLM gates pass); the ADR describes a port, not a missing feature.

## Negative results (claims that were attacked and held)

Across the six dimensions, 64 distinct claims were attacked and could **not** be broken — including
the ledger tamper battery (payload edit, reorder, truncate-with-anchor, full re-chain), tenant
isolation on every read method, zero-egress across the full lifecycle **including the index path**,
the NullModelProvider running the whole core, and `rebuild_projection == replay` equality. These are
the load-bearing invariants; they survived the adversarial pass.

## Gate

`ADVERSARIAL_AUDIT = PASS` — every material finding became a red test before its fix; 0 material
findings remain open (residuals above are LOW/KNOWN_GAP or FUTURE, documented, non-blocking).
