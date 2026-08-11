# License Matrix & Clean-Room Attestation

## EPISTEMOS license

**Apache-2.0** (`LICENSE`, `pyproject.toml: license = "Apache-2.0"`). See ADR-015 for the rationale
(permissive, patent grant, compatible with the permissive tool/ecosystem, safe for the intended
adapter integrations with NOMOS/Hermes/OpenClaw).

## Compatibility of everything we depend on

| Component | License | Runtime? | Compatible with Apache-2.0? |
|-----------|---------|----------|:--:|
| **epistemos runtime** | Apache-2.0 | — | — (this project) |
| Python stdlib | PSF-2.0 | yes (only runtime code) | ✔ |
| hatchling (build) | MIT | no (build only) | ✔ |
| pytest / ruff / mypy | MIT | no (dev only) | ✔ |
| pluggy / iniconfig / mypy-extensions | MIT | no | ✔ |
| pygments | BSD-2-Clause | no | ✔ |
| packaging | Apache-2.0 / BSD-2 | no | ✔ |
| typing-extensions | PSF-2.0 | no | ✔ |
| pathspec | MPL-2.0 | no (dev only, not linked/distributed) | ✔ |

No copyleft license affects the EPISTEMOS distribution: the runtime has **zero** third-party code,
and MPL-2.0 (pathspec) is a dev-only tool dependency that is neither modified nor redistributed.

## Clean-room attestation (mission §43)

```
NOT_A_FORK               = TRUE
NO_UNATTRIBUTED_CODE     = TRUE
LICENSES_VALIDATED       = TRUE
ARCHITECTURE_OWNED       = TRUE
CORE_IMPLEMENTATION_OWNED= TRUE
```

**Evidence:**

- **Not a fork:** the repository was `git init`-ed fresh (root commit in this repo's history); it
  is not a clone or fork of any surveyed project. The census projects were studied for *concepts,
  algorithms, data models, and published standards only* — see `docs/research/`.
- **No copied code:** the implementation is stdlib-only Python written for this repo. What was
  learned from prior art is **conceptual** (bitemporality, PROV Entity/Activity/Agent, invalidate-
  don't-delete, hexagonal ports) and is documented as such in `docs/research/FEATURE_HARVEST.md`.
  Concepts and published standards are not copyrightable expression.
- **Standards referenced (not vendored):** W3C PROV-DM/PROV-O, SQL:2011 bitemporal semantics, the
  MCP JSON-RPC shape, and the CycloneDX SBOM idea are open specifications; EPISTEMOS implements
  compatible behavior, it does not copy any reference implementation.
- **Third-party code incorporated:** **none** (runtime deps = 0). Any future incorporation must,
  per the mission, carry an explicit validated license, recorded origin, demonstrated architectural
  need, and correct attribution.
