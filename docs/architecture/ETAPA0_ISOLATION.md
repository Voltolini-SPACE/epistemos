# ETAPA 0 — Environment Rebaseline & Isolation

## Host (measured 2026-08-11)

| Property | Value |
|----------|-------|
| OS | macOS 26.3.1 (Darwin 25.3.0), arm64 (Apple Silicon T6020) |
| Python | 3.14.5 (`/opt/homebrew/bin/python3`); `sqlite3` 3.53.4 |
| Node | v22.23.1 |
| Docker | 29.5.3 |
| git | 2.50.1 |
| Disk | Data volume 358 GiB used / 74 GiB free (83%); root ok |
| Toolchain | `uv` 0.11.14, `pytest` 9.0.3 present; `ruff`/`mypy` installed into repo venv |

## Repository location — decision

**Chosen:** `~/Projects/epistemos` (not the mission-suggested `~/Desktop/EPISTEMOS_REPO/epistemos`).

**Rationale:** the durable host convention is that *code lives in `~/Projects/<name>`*
(every real code project on this host is there; `~/Desktop` is an audit/artifact/app area).
The mission (§2) explicitly delegates this: *"Se essa convenção não fizer sentido no host,
resolver um local seguro e registrar a decisão."* This is that registration. The engineering
name **EPISTEMOS** is unchanged; only the on-disk path differs from the suggestion.

- `git init -b main`; work branch `feat/epistemos-01-bootstrap`.
- Target path was **free** before creation (no collision).

## Isolation guarantees

All writes for this mission occur **only** under `~/Projects/epistemos`. No existing system
is modified. Read-only baseline captured at start (re-verified at freeze):

```
NOMOS   ~/Desktop/NOMOS_REPO/nomos   HEAD=2cea197eb188121fcd507b53f02935b5edf435ad  (pre-existing 2 dirty lines — NOT touched)
NOMOS   ~/.nomos                     mtime 2026-08-09T20:05:59
HERMES  ~/.hermes                    mtime 2026-07-30T03:43:50
OPENCLAW ~/.openclaw                 mtime 2026-08-11T12:48:02
HERMES  ~/Projects/hermes-dspy-integration       mtime 2026-08-09T17:36:30
NOMOS   ~/Projects/nomos-hermes-architecture     mtime 2026-08-09T18:36:23
```

Proven at freeze:

```
CONCURRENT_WRITER    = FALSE   (single session; no daemon writes into the repo)
NOMOS_UNTOUCHED      = TRUE    (HEAD + dirty-count unchanged; mtimes unchanged)
HERMES_UNTOUCHED     = TRUE
OPENCLAW_UNTOUCHED   = TRUE
PRODUCTION_UNTOUCHED = TRUE    (core is zero-egress; no production endpoint contacted)
```

## Integration boundary (this mission)

Integration with NOMOS / Hermes / OpenClaw is **forbidden** in EPISTEMOS-01. Only *contracts*
(`adapters/*/` specs, `docs/integration/`) are produced. `CORE ← ADAPTER` dependency direction
is enforced; the core imports nothing from any existing system.
