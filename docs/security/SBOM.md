# SBOM — Software Bill of Materials

Format: CycloneDX-style (minimal). Generated 2026-08-11. Scope split into **runtime** (what ships /
executes in production) and **dev/build** (not distributed, not in the runtime path).

## Runtime SBOM

The runtime component graph is a single node: EPISTEMOS itself. There are **no third-party runtime
components** — the only executing non-project code is the Python standard library.

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "metadata": {
    "component": {
      "type": "library",
      "name": "epistemos",
      "version": "0.1.0",
      "licenses": [{ "license": { "id": "MIT" } }],
      "purl": "pkg:pypi/epistemos@0.1.0"
    },
    "properties": [
      { "name": "runtime_dependencies", "value": "0" },
      { "name": "runtime_platform", "value": "CPython stdlib only (>=3.11)" }
    ]
  },
  "components": []
}
```

## Dev / build SBOM (not distributed)

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "components": [
    { "type": "application", "name": "hatchling", "scope": "build", "licenses": [{"license":{"id":"MIT"}}] },
    { "type": "application", "name": "pytest", "version": "9.1.1", "scope": "test", "licenses": [{"license":{"id":"MIT"}}], "purl": "pkg:pypi/pytest@9.1.1" },
    { "type": "application", "name": "ruff", "version": "0.16.2", "scope": "lint", "licenses": [{"license":{"id":"MIT"}}], "purl": "pkg:pypi/ruff@0.16.2" },
    { "type": "application", "name": "mypy", "version": "2.3.0", "scope": "typecheck", "licenses": [{"license":{"id":"MIT"}}], "purl": "pkg:pypi/mypy@2.3.0" },
    { "type": "library", "name": "pluggy", "version": "1.6.0", "scope": "test-transitive", "licenses": [{"license":{"id":"MIT"}}] },
    { "type": "library", "name": "iniconfig", "version": "2.3.0", "scope": "test-transitive", "licenses": [{"license":{"id":"MIT"}}] },
    { "type": "library", "name": "packaging", "version": "26.3", "scope": "transitive", "licenses": [{"license":{"id":"Apache-2.0"}}] },
    { "type": "library", "name": "pygments", "version": "2.20.0", "scope": "test-transitive", "licenses": [{"license":{"id":"BSD-2-Clause"}}] },
    { "type": "library", "name": "mypy-extensions", "version": "1.1.0", "scope": "typecheck-transitive", "licenses": [{"license":{"id":"MIT"}}] },
    { "type": "library", "name": "typing-extensions", "version": "4.16.0", "scope": "typecheck-transitive", "licenses": [{"license":{"id":"PSF-2.0"}}] },
    { "type": "library", "name": "pathspec", "version": "1.1.1", "scope": "typecheck-transitive", "licenses": [{"license":{"id":"MPL-2.0"}}] }
  ]
}
```

## Attestations

- **Runtime third-party components:** 0.
- **License classes present:** Apache-2.0, MIT, BSD-2-Clause, PSF-2.0, MPL-2.0 — all permissive,
  all Apache-2.0-compatible; none in the runtime artifact.
- **Provenance:** all dev/build components are published PyPI wheels installed via `uv`; no vendored
  binaries, no install-time network fetches beyond PyPI, no build scripts authored by EPISTEMOS.

Regenerate the inventory with `uv pip list`; see `DEPENDENCY_INVENTORY.md`.
