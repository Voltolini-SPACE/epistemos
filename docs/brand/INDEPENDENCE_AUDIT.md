# EPISTEMOS — Independence Audit

Proof that EPISTEMOS is an **independent product**, not a component of NOMOS/Hermes/OpenClaw.

## Core has no dependency on any other product

```
$ git grep -nE '^\s*(import|from)\s+.*(nomos|hermes|openclaw)' -- 'src/epistemos/**'
(no matches)
```

```
CORE_DEPENDS_ON_NOMOS    = FALSE
CORE_DEPENDS_ON_HERMES   = FALSE
CORE_DEPENDS_ON_OPENCLAW = FALSE
```

The only `nomos/hermes/openclaw` strings inside `src/epistemos/` are **explanatory docstrings** (e.g.
`identity/__init__.py` states that NOMOS is the policy authority and that EPISTEMOS *never grants
capabilities*). They describe positioning; they are not imports or runtime references.

## Where those names legitimately appear (allowed)

- `docs/integration/` — adapter **specifications** (NOMOS/Hermes/OpenClaw/generic MCP), contracts only.
- `adapters/*/README.md` — placeholder homes; `CORE ← ADAPTER`, adapters depend on EPISTEMOS, never
  the reverse.
- `README.md`, `docs/adr/ADR-013-adapter-architecture.md`, brand docs — positioning.

No integration code ships. Those integrations are **adapter-ready / planned**, each gated behind its
own future mission (`EPISTEMOS-NOMOS-01`, etc.).

## Package identity

- Python package / import: `epistemos` (`import epistemos`). No fundamental API requires a
  NOMOS/Hermes/OpenClaw name.
- Repo: `github.com/Voltolini-SPACE/epistemos` (independent). Versions: `epistemos-vX.Y.Z`.
- Runtime third-party dependencies: **0** (`pyproject.toml: dependencies = []`).

## Supply chain / license

MIT. Zero runtime dependencies ⇒ no runtime supply chain. See
[`../security/LICENSE_MATRIX.md`](../security/LICENSE_MATRIX.md), `DEPENDENCY_INVENTORY.md`, `SBOM.md`.
