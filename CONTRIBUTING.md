# Contributing to EPISTEMOS

Thanks for your interest. EPISTEMOS is a clean-room, local-first engine with **zero third-party
runtime dependencies** and a high evidence bar — please keep both intact.

## Development setup

```bash
git clone https://github.com/Voltolini-SPACE/epistemos && cd epistemos
uv venv --python 3.14 .venv && . .venv/bin/activate   # or python -m venv
uv pip install -e ".[dev]"                            # dev extras: pytest, ruff, mypy
```

## Before you open a PR

Everything must be green:

```bash
python -m pytest tests/unit tests/security tests/race tests/chaos tests/integration tests/index
ruff check src tests
mypy --strict src/epistemos
python tools/mutation_harness.py       # critical-boundary mutation (0 survivors)
```

## Ground rules

- **No third-party runtime dependencies.** The core is standard-library only. New runtime deps need
  a strong justification and an ADR.
- **No network calls in the core** (zero-egress) and **no mandatory LLM** (`NullModelProvider` must
  keep passing). Model/vector features are optional and behind a port.
- **Evidence over assertion.** New behavior needs tests; new invariants get a mutation-harness mutant;
  performance claims get a benchmark. A green suite is necessary, not sufficient.
- **Preserve invariants:** bitemporal semantics, provenance, tamper-evident ledger, fail-closed
  tenancy, storage abstraction, explainable retrieval, index-as-rebuildable-projection.
- **Architecture decisions** go in `docs/adr/` (Status / Context / Decision / Consequences / Rejected
  alternatives).
- **Commits** are small and prefixed (`core:`, `test:`, `security:`, `bench:`, `docs:`, `fix:`).

## Licensing

By contributing you agree your contributions are licensed under **Apache-2.0** (inbound = outbound).

## Security

Please report vulnerabilities privately — see [`SECURITY.md`](SECURITY.md). Do not open public issues
for security reports.
