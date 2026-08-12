# EPISTEMOS Panel — Surface Inventory (EPISTEMOS-PANEL-HARDENING-01, §3)

Baseline: core `epistemos-v0.5.0` + `epistemos-panel-v1`. Server: `src/epistemos/api/server.py`
(`ThreadingHTTPServer`, `daemon_threads`, `HTTP/1.1`, binds `127.0.0.1`). Read-model:
`api/panel.py`. Stream: `api/stream.py`. Auth: `api/rest.py::StaticTokenAuth`.

Trust boundary: **the browser and the network are untrusted**. Identity comes only from the bearer
token (`Authorization: Bearer` header) or the `eps_session` cookie set by `POST /api/session`; it
resolves to a `Principal` server-side. The client cannot choose tenant/namespace-authority/
capability/visibility. The panel is **read-only** — no mutating route exists.

## HTTP surface

| SURFACE | METHOD | AUTH | ROLE | INPUT | SIDE_EFFECT | FAILURE_MODE | CURRENT_TEST | GAP |
|---|---|---|---|---|---|---|---|---|
| `/` and static (`app.js`,`styles.css`,…) | GET | no | none | path | none (read file) | 404 / traversal-guarded | test_server CSP | none (traversal guarded via commonpath) |
| `/api/session` | POST | token in body | none | `{token}` | sets `eps_session` cookie | 401 unknown token | test_server cookie | none |
| `/api/whoami` | GET | optional | none | cookie/header | none | 200 `{authenticated:false}` w/o token | test_server | none |
| `/api/overview` | GET | yes | read | cookie/header | none | 401 unauth | leak+server | none |
| `/api/counts` | GET | yes | read | — | none | 401 | leak | none |
| `/api/graph` | GET | yes | read | `focus,hops,kinds,limit` | none | **`hops`/`limit` non-int → 500** | leak+server | **F1 input-validation** |
| `/api/graph/expand` | GET | yes | read | `node` | none | **missing `node` → 500** | leak | **F1** |
| `/api/list` | GET | yes | read | `kind,limit,offset` | none | bad `kind`→400; **`limit/offset` non-int→500** | leak | **F1** |
| `/api/claim` | GET | yes | read | `id` | none | **missing `id` → 500**; unreadable→404 | leak | **F1** |
| `/api/belief` | GET | yes | read | `id` | none | missing `id`→500; unreadable→404 | leak | **F1** |
| `/api/evidence` | GET | yes | read | `id` | none | missing `id`→500; unreadable→404 | leak | **F1** |
| `/api/explain` | GET | yes | read | `id` | none | missing `id`→500; unreadable→404 | leak | **F1** |
| `/api/activity` | GET | yes | read | `since,limit` | none | non-int→500 | — | **F1** |
| `/api/asof` | GET | yes | read | `at,kinds` | none | missing `at`→500; malformed `at`→lexical filter | — | **F1 + F2 time-travel state** |
| `/api/spaces` | GET | yes | read | — | none | 401 | — | thin |
| `/api/agents` | GET | yes | read | — | none | 401 | — | thin |
| `/api/sources` | GET | yes | read | — | none | 401 | — | thin |
| `/api/health` | GET | yes | read | — | none | 401 | — | verify health output has no internals |
| `/api/search` | GET/POST | yes | read | `text,subject,predicate,object,kinds,limit,believed_only` | none | POST `limit` non-int→500 | leak+server | **F1** |
| `/api/stream` | GET (SSE) | yes | read | `Last-Event-ID` header | none | 401 unauth; bad id→since=0 (handled) | stream | verify unauth closes; measure loss/dup |

## Non-HTTP surface

| SURFACE | NOTES |
|---|---|
| CLI `python -m epistemos.panel [--demo\|--db\|--live-demo] [--port]` | entrypoint; `--live-demo` spawns a background WRITER thread on the same Engine |
| SSE poll | `authorized_events` re-reads ledger `since_seq` each 1s; `_STREAM_HEARTBEAT=15s`; O(N) MemoryStore / indexed SQLite |
| Cookie `eps_session` | value = raw bearer token; `HttpOnly; SameSite=Strict; Path=/; Max-Age=86400`; **no `Secure`** (local-first HTTP, acceptable) |
| localStorage/sessionStorage | none used by the app (token is HttpOnly cookie, not JS-readable) — verify empirically |
| CORS | none (no `Access-Control-Allow-Origin`); same-origin only |
| CSP | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'` |
| Security headers | `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Cache-Control: no-store` on every response |
| Logging | `log_message` silenced (no stdout/stderr request logging) → no request-log secret leak |
| Concurrency | `ThreadingHTTPServer` + shared `Engine`; **store serializes all ops under `RLock`** (MemoryStore) / connection lock (SQLite); `objects()`/`read_events()` snapshot under lock |

## Candidate findings from inventory (to reproduce empirically)

- **F1 (reliability + minor info-leak, class: input-validation):** malformed or missing query/body
  params reach `int(...)` / `q["id"]` and raise `ValueError`/`KeyError`, which the boundary maps to
  **HTTP 500** with the raw Python message (`_fail` sends `str(exc)` for 5xx). Should be **400
  ValidationError** with a safe message. Endpoints: graph, list, claim, belief, evidence, explain,
  activity, asof, expand, search(POST).
- **F2 (time-travel semantics, class: correctness/possible future-state exposure):** `panel.as_of`
  filters object *existence* by `str(tx_from) <= at_tx` but projects the object's **current** mutable
  fields (e.g. `status`, `metadata.accepted/rejected`). Must verify `FUTURE_KNOWLEDGE_LEAK = 0` for
  displayed *state*, not only existence. Also malformed `at` degrades to a lexical comparison.
- **Verify:** `/api/health` output carries no filesystem path / internal secret.
- **Verify:** unauth `/api/stream` returns 401 and does not open a stream.
