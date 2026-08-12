# Dependency Inventory

Generated 2026-08-11 from the project venv (`uv pip list`) and package metadata.

## Runtime dependencies

**NONE.** `epistemos`'s declared runtime `dependencies = []` (see `pyproject.toml`). Importing
the package pulls in only the Python **standard library** (`sqlite3`, `hashlib`, `json`, `uuid`,
`datetime`, `http.server`, `socketserver`, `re`, `dataclasses`, `enum`, …). Verified:

```
$ python -c "import epistemos, sys; ..."
non-stdlib modules imported by epistemos: []   # (sitecustomize is venv machinery, not a dep)
```

This is the strongest possible supply-chain posture for the core: no third-party runtime code,
no transitive runtime advisories, nothing to pin.

## Build dependency (build-time only)

| Package | Version | License | Role |
|---------|---------|---------|------|
| hatchling | (build backend) | MIT | PEP 517 wheel/sdist build |

## Development dependencies (`[project.optional-dependencies].dev`)

| Package | Version | License | Why |
|---------|---------|---------|-----|
| pytest | 9.1.1 | MIT | test runner |
| ruff | 0.16.2 | MIT | lint + format (standalone Rust binary, no Python deps) |
| mypy | 2.3.0 | MIT | static type checking |
| pluggy | 1.6.0 | MIT | (pytest transitive) |
| iniconfig | 2.3.0 | MIT | (pytest transitive) |
| packaging | 26.3 | Apache-2.0 / BSD-2 | (pytest/mypy transitive) |
| pygments | 2.20.0 | BSD-2-Clause | (pytest transitive, tracebacks) |
| mypy-extensions | 1.1.0 | MIT | (mypy transitive) |
| typing-extensions | 4.16.0 | PSF-2.0 | (mypy transitive) |
| pathspec | 1.1.1 | MPL-2.0 | (mypy transitive) |

All dev/build licenses are permissive and MIT-compatible (MIT / BSD / Apache-2.0 / PSF /
MPL-2.0). None are copyleft in a way that affects EPISTEMOS's MIT distribution, and none
ship in the runtime artifact.

### Environment note (honest disclosure)

The shared venv also lists `ast-serialize 0.8.0` and `librt 0.15.0`. These are **not** declared or
required by EPISTEMOS or its dev tools; they are pre-existing host/venv artifacts. They are recorded
here for transparency and are excluded from the EPISTEMOS SBOM.

## Policy checks (mission §27)

- **Direct deps:** runtime 0, dev 3 (all MIT).
- **Transitive deps:** runtime 0; dev transitive all permissive (table above).
- **Unpinned:** dev deps use floors (`>=`) for local dev; a release should pin exact versions.
- **Install scripts / binary downloads:** ruff is a prebuilt binary from PyPI wheels (standard).
  No `postinstall`/`preinstall` scripts, no curl-to-shell, no vendored binaries in the repo.
- **Known advisories:** none apply to a zero-runtime-dependency package; dev tools are current.
