# Deployment

The panel is **local-first** and runs with no cloud dependency. It is **not** the marketing page at
`voltolini.space/epistemos` — that stays a product/marketing profile; this is the operational
interface, deployed separately (mission §47).

## Run it

```bash
# demo: a real corpus (real objects via the real Engine API) + a demo login picker, in-memory
python -m epistemos.panel --demo

# demo with a live generator (real ledger activity for the realtime stream)
python -m epistemos.panel --demo --live-demo

# real: serve a persisted SQLite-backed Engine; identities come from the environment
EPISTEMOS_PANEL_TOKENS="s3cret=alice,t0ken=bob" \
EPISTEMOS_PANEL_TENANT=acme EPISTEMOS_PANEL_NAMESPACE=kb \
python -m epistemos.panel --db /path/to/knowledge.db --port 8787
```

Binds `127.0.0.1` by default; open `http://127.0.0.1:<port>/`. Nothing leaves the machine — a strict
`default-src 'self'` CSP blocks any external request, and the core is zero-egress.

## Modes

- **`--demo`** (default when no `--db`): in-memory Engine seeded with a real demo corpus; demo
  identities are exposed for the login picker (demo tokens only).
- **`--db PATH`**: a real, persisted `SQLiteStore` Engine. Tokens come from `EPISTEMOS_PANEL_TOKENS`
  (`token=agent` pairs); **no** identities are exposed for a real store. This is the production shape:
  a local (or self-hosted) app over your own knowledge base.
- **`--live-demo`**: additionally runs a slow real-object generator so the SSE stream shows genuine
  ledger activity.

## Deployment shapes

- **Local application / localhost web app** — the default. Single `python -m epistemos.panel`, no
  server infrastructure, works offline.
- **Self-hosted panel** — run behind your own reverse proxy/auth on a trusted host; the panel still
  authenticates every request server-side and holds the zero-egress CSP. Terminate TLS at the proxy;
  the session cookie is HttpOnly + SameSite=Strict.
- **Hosted frontend (optional)** — possible but never required; local/self-hosted must always work
  without cloud.

## Dependencies

Zero third-party runtime dependencies (stdlib only) — the panel server and the vanilla frontend add
none. `pip install epistemos` then `python -m epistemos.panel` is the whole install.
