# EPISTEMOS Panel — Hardening Report (EPISTEMOS-PANEL-HARDENING-01)

Turning the published `epistemos-panel-v1` into a measured, adversarially validated,
production-grade candidate. Every finding followed
`DETECT → REPRODUCE → CLASSIFY → FIX → REGRESSION TEST → ADVERSARIAL RETEST → FULL SUITE`.

```text
STATUS_FINAL = EPISTEMOS_PANEL_HARDENING_PASS

BASELINE_HEAD = ab45c3c  (core epistemos-v0.5.0 + epistemos-panel-v1)
FINAL_HEAD    = ea929f2
BRANCH        = mission/epistemos-panel-hardening-01
COMMITS       = e157b59 F1/F3/F4 + inventory   · 349ea5b XSS/H3   · 572f0ae race/H5
                d02dcc7 FUTURE_KNOWLEDGE_LEAK/H7 · fd4a698 failure+integrity/H6
                (SSE/H4) · 7571f8a perf single-pass · 41c83d0 a11y+responsive/H8+H9
                68989df headers/H10 · ea929f2 mutation+chaos/H11

TESTS         = 928 passed  (baseline 877 + 51 new hardening; +6 files)
RUFF          = clean (src tests)          MYPY --strict = clean (38 files)
MUTATION      = panel boundaries 9/9 KILLED, SURVIVED=0  (tools/mutation_panel.py)
RACE          = 30 rounds / 360 reader batches, ERRORS=0
CHAOS         = projection rebuild byte-identical + firewall holds; storage-fault = explicit 500
SOAK          = 90 s, threads 9→11 / fds 10→14 bounded (no leak); RSS growth = corpus growth
ACCESSIBILITY = 0 structural + 0 contrast issues across 8 screens (automated DOM sweep)
RESPONSIVE    = 0 horizontal overflow at 320/375/430/768/1024/1440/1920
FRESH_CLONE   = install + engine quickstart + panel start + auth + overview/graph/list/health/asof
                + SSE + shutdown, all from a clean clone of FINAL_HEAD

AUTH          = PASS  (missing/invalid/truncated/oversized/forged tokens rejected; no client-authority)
AUTHZ         = PASS  (horizontal/vertical/priv-esc blocked; no forbidden-vs-absent oracle)
XSS           = PASS  (payloads inert as text; innerHTML sink removed; CSP self-only)
SSE           = PASS  (EVENT_LOSS=0, DUPLICATE_RATE=0, ordered, reconnect-resume clean)
BITEMPORAL    = PASS  (FUTURE_KNOWLEDGE_LEAK = 0)
PROVENANCE    = PASS  (belief→evidence→source→review chain reachable; absence shown, never faked)
SECRET_LEAK   = PASS  (no token/secret in body/headers/logs/storage; 5xx generic; Server ver hidden)
PERFORMANCE   = PASS  (measured 100/1k/10k; single-pass optimization 3–5× on aggregate views)

BUGS_FOUND    = 6   BUGS_FIXED = 6   (+1 test-coverage gap exposed by mutation, fixed)
RESIDUAL_RISKS   = O(N) read-model beyond ~10k objects (cached index = future work);
                   soak proven for 90 s only (not multi-hour); manual screen-reader pass recommended
DEFERRED_ITEMS   = per-principal authorized index; multi-hour soak; axe-core CI once CSP-compatible

NOMOS_UNCHANGED    = TRUE  (2cea197e, byte-identical)
HERMES_UNCHANGED   = TRUE  (no standalone repo in ~/Projects; not touched — all work in epistemos)
OPENCLAW_UNCHANGED = TRUE  (idem)
```

## Bugs

### H-01 · FUTURE_KNOWLEDGE_LEAK in time-travel — **HIGH**
- **ATTACK/FAILURE:** `as_of(at_tx)` filtered object *existence* by `tx_from ≤ at_tx` but projected each object's **current** mutable state, so a claim retracted/accepted *after* `at_tx` displayed its future status, and evidence attached later still drew an edge. Viewing the past leaked the future.
- **REPRODUCTION:** create claim → capture midpoint `at_tx` → retract claim; `as_of(midpoint)` showed `status="retracted"`.
- **ROOT_CAUSE:** state read from the live projection, not reconstructed from the ledger at `at_tx`.
- **FIX:** `_asof_state` scans the ledger using only events with `ts ≤ at_tx`; `_project_node_asof` derives claim status / fact belief as-of; `_edges_asof` takes evidence links from the as-of ledger, not current metadata. (`panel.py`)
- **REGRESSION:** `tests/panel/test_bitemporal.py::test_future_knowledge_leak_is_zero`.
- **ADVERSARIAL RETEST:** mutants `asof_include_future_events`, `asof_status_ignore_retraction` — both KILLED.
- **STATUS:** FIXED. `FUTURE_KNOWLEDGE_LEAK = 0`.

### H-02 · HTTP request smuggling via undrained POST body — **MEDIUM-HIGH**
- **ATTACK/FAILURE:** an errored POST (e.g. 401 before `_body()`) left the declared body on the keep-alive socket; the next parse started mid-body. Proven: a smuggled `GET /api/overview` executed as a second response (`responses=2`).
- **ROOT_CAUSE:** panel `do_POST` lacked the body-drain that `rest.py` already had (B-05 parity).
- **FIX:** `_drain_body` + `_body_consumed` tracking; over-limit bodies close the connection instead of being read. (`server.py`)
- **REGRESSION:** `test_hardening_http.py::test_errored_post_body_is_not_smuggled` (`responses ≤ 1`).
- **ADVERSARIAL RETEST:** mutant `post_skip_body_drain` — KILLED.
- **STATUS:** FIXED.

### H-03 · Malformed/missing params → 500 + internal Python text — **MEDIUM**
- **ATTACK/FAILURE:** `hops/limit/offset/since` non-int and missing `id/node/at` reached `int()`/`q[key]` → HTTP **500** echoing `invalid literal for int()` / `'id'`.
- **FIX:** `_qint`/`_qreq`/`_safe_int` → **400** with a safe, parameter-named message; 5xx bodies never echo `str(exc)`; invalid-JSON message genericized. (`server.py`)
- **REGRESSION:** `test_hardening_http.py::test_malformed_param_is_400_not_500` (10 params) + `test_search_post_bad_limit_is_400`.
- **ADVERSARIAL RETEST:** mutants `qint_swallow_bad_value`, `qreq_return_empty_not_raise`, `fail_leak_5xx_message` — all KILLED.
- **STATUS:** FIXED.

### H-04 · `Server` header advertised the Python version — **LOW**
- **ATTACK/FAILURE:** `Server: epistemos-panel/1.0 Python/3.14.5` (runtime fingerprinting).
- **FIX:** `version_string()` returns only `server_version`. (`server.py`)
- **REGRESSION:** `test_server_header_hides_python_version` — asserts the **exact** header value (tightened after the mutation run below).
- **ADVERSARIAL RETEST:** mutant `server_version_leak_python` initially **SURVIVED** (test only checked `Python/` absent) → test strengthened → re-run KILLED.
- **STATUS:** FIXED (bug + the test-coverage gap it exposed).

### H-05 · Accessibility (WCAG AA) violations — **MEDIUM**
- **FAILURE:** graph screen had no heading; timeline date input was unlabeled; overview/spaces skipped heading levels (h1→h3); muted text (`--fg-3`) and the retracted badge were 4.15–4.27:1 (< 4.5:1); no `aria-live` on the realtime feed/connection.
- **FIX:** accessible `<h1>` for the graph; `aria-label` on the time-travel input; section titles → `<h2>`; `--fg-3` and retracted badge raised to clear 4.5:1; `role="log"`+`aria-live` on the feed, `role="status"` on the connection. (`screens.js`, `app.js`, `styles.css`)
- **REGRESSION:** automated DOM sweep → 0 structural + 0 contrast issues across 8 screens (`MEASUREMENTS.md`); XSS structural guard already pins the frontend.
- **STATUS:** FIXED. *Caveat:* manual screen-reader pass still recommended.

### H-06 · Horizontal overflow at 320 px — **MEDIUM**
- **FAILURE:** 320 px viewport scrolled to 358 px — the activity-feed summary and the topbar/main grid items forced width beyond the viewport.
- **FIX:** `min-width:0` on `.ev .s`, `.topbar`, `.main` (flex/grid items must shrink below content). (`styles.css`)
- **REGRESSION:** live overflow check → 0 issues at 320/375/430/768/1024/1440/1920.
- **STATUS:** FIXED.

## Non-bug improvement

**Single-pass read-model** — the aggregate views scanned the store once per kind (7 passes). `_readable_by_kinds` does one bucketed pass: at 10k objects, counts 317→97 ms, overview 363→135 ms, graph 298→86 ms, as_of 274→52 ms (3–5×), identical semantics (pinned by `test_readmodel_perf_equiv.py`). This also halved the race-battery wall-clock (73 s → 35 s).

## Verdict

The evidence supports operating the EPISTEMOS Panel under real use without blind trust in the
implementation: the authorization firewall holds over HTTP, under concurrency, on the stream, and
after a crash-rebuild; time-travel no longer leaks the future; inputs fail closed; and the
boundaries are pinned by regressions that mutation testing proves are non-vacuous. The residual
risks (O(N) read-model beyond ~10k, 90-second soak, manual SR pass) are documented, not hidden.
