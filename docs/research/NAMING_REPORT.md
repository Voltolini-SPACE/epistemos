# NAMING REPORT — "EPISTEMOS"

**Date:** 2026-08-11 · **Method:** live web census (GitHub, PyPI, npm, near-neighbour scan).
This is an engineering-name assessment, **not** a legal trademark clearance.

## Findings (MEASURED unless noted)

| Surface | Result | Evidence |
|---------|--------|----------|
| **PyPI** `epistemos` | **AVAILABLE** | `https://pypi.org/pypi/epistemos/json` → HTTP 404 |
| **npm** `epistemos` | **AVAILABLE** | `https://registry.npmjs.org/epistemos` → HTTP 404 |
| **GitHub** repo/org `epistemos` | No notable exact match found | census web search |
| **crates.io** | Not relevant (no Rust crate planned for v0.1) | — |
| Near-neighbour `episteme` | **CROWDED in this niche** | e.g. `junjslee/episteme` ("portable cognitive kernel for AI agents", MIT); `epicsagas/episteme` |
| Near-neighbour `epistemic`/`epistemy` | Common as adjectives/blog names | general web |

## Assessment

- The **exact** engineering name `epistemos` is free on the three registries that matter for
  this project (PyPI, npm, GitHub). No exact collision was found.
- The **semantic neighbourhood** (`episteme`, `epistemic`) is busy, including at least one
  AI-agent "cognitive kernel" project. This is a *brand-confusion* risk, not a namespace
  collision. It does not block internal development or an internal `pip install epistemos`.

## Verdict

```
NAMING_INTERNAL        = PASS      (exact name free on PyPI/npm/GitHub; unchanged per mission §3)
PUBLIC_BRAND_CLEARANCE = PENDING   (no formal trademark search performed — do not claim clearance)
```

Per mission §AI, this does **not** block the internal v0.1 tag. Before any *public* release,
run a formal trademark/brand search. If a material public collision is confirmed, the census
proposed same-family alternatives (INFERRED availability, re-verify before use):

> Mnemos · Anamnesis · Hypomnema · Noesis · Engram · Provena

The engineering name remains **EPISTEMOS** for this mission.
