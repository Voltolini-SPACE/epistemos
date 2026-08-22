# EPISTEMOS — Product Inventory (Freeze 2026.08)

Everything public, in one place, so nothing is forgotten at freeze.

| Surface | What | Location / URL | State |
|---|---|---|---|
| **Core** | Sovereign bitemporal engine (ledger, spaces, claims, temporal, provenance, retrieval) | `src/epistemos/` | v0.7.0 |
| **Context Envelope** | Post-retrieval evidence-preserving compaction | `src/epistemos/context/` | v0.6, stable |
| **EPCTX/1** | Provider-agnostic context protocol (wire, serialization, versioning, handles, renderer) | `src/epistemos/protocol/` | v0.7, stable |
| **SDK** | Local + Remote clients (search/context/EPCTX/expand/health) | `src/epistemos/sdk.py`, `protocol/client.py` | stable |
| **REST** | localhost HTTP boundary (`POST /context`, `/search`, `/facts`, …) | `src/epistemos/api/rest.py` | stable |
| **MCP** | Hostile-frontier tool server (`epistemos_context`, …) | `src/epistemos/mcp/` | stable |
| **Panel** | Local-first operational UI (graph, claims, evidence, timeline, spaces, health, live SSE) | `src/epistemos/panel/` | v1.1 |
| **README** | Product page + technical onboarding | `README.md` | current |
| **Docs** | architecture, protocol, context, claims, spaces, panel, security, integrations, benchmarks, adr, brand, research, final | `docs/` | current |
| **ADRs** | 044 decision records incl. superseded + negative results | `docs/adr/` (README index) | current |
| **Benchmarks** | Reproducible methodology + results | `docs/benchmarks/`, `tools/eps0*_benchmark.py` | current |
| **Integration specs** | Generic agent + NOMOS / Hermes / OpenClaw (spec-only) | `docs/integrations/` | planned |
| **License** | MIT | `LICENSE`, `pyproject.toml` | MIT |
| **Security** | Threat model, SBOM, zero-egress, mutation report | `docs/security/` | current |
| **GitHub** | Repo, releases, tags | github.com/Voltolini-SPACE/epistemos | public |
| **Releases** | v0.1 … v0.7, panel-v1, panel-v1.1 | GitHub Releases | intact |
| **Site** | Product page | voltolini.space/epistemos | live |
| **Brand** | Product profile, brandbook, independence audit | `docs/brand/` | current |
| **Social / OG** | og-image, favicon | `voltolini-space-site/assets/epistemos-*` | live |

## Tests / gates at freeze

- **1007 tests** (core + panel + protocol + CLI), ruff + mypy `--strict` clean.
- Mutation: 39/39 claim core, 9/9 panel, 6/6 Context Envelope, 7/7 EPCTX protocol.
- Leak invariants at zero: tenant / space / claim / EPCTX / expansion / panel-UI / graph / search / stream.
- Zero-egress (core), no mandatory LLM, zero runtime dependencies.

See [PUBLIC_CLAIMS_AUDIT.md](PUBLIC_CLAIMS_AUDIT.md) and
[EPISTEMOS_PRODUCT_FREEZE_FINAL.md](EPISTEMOS_PRODUCT_FREEZE_FINAL.md).
