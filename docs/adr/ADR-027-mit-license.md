# ADR-027 — Relicense to MIT

**Status:** Accepted (v0.4) — supersedes the license choice of [ADR-015](ADR-015-licensing-strategy.md)

## Context

ADR-015 chose Apache-2.0 for v0.1 (permissive + explicit patent grant). For the public product the
owner decided (EPISTEMOS-04 addendum) to standardise on the **MIT License**: maximally simple,
maximally permissive, the most widely recognised OSI license for a small clean-room library, and
what GitHub's license detector and downstream packagers handle most frictionlessly.

## Decision

EPISTEMOS is distributed under the **MIT License** from the v0.4 baseline forward.

- `LICENSE` is the verbatim official MIT text; copyright holder **Voltolini (voltolini.space)**,
  year **2026** (matching the existing `NOTICE` attribution). No clause is modified — a modified MIT
  is not MIT.
- `pyproject.toml`: `license = "MIT"`, classifier `License :: OSI Approved :: MIT License`.
- `NOTICE` (an Apache convention, not required by MIT) is trimmed to a short MIT copyright + the
  clean-room attestation, and kept for continuity.
- README, CONTRIBUTING, brand/product docs, `LICENSE_MATRIX`, `SBOM`, `DEPENDENCY_INVENTORY`, and the
  competitor matrix's EPISTEMOS row all state MIT.

### Provenance audit (why MIT is unencumbered)

- **Zero third-party runtime code.** The runtime is Python standard library only (`dependencies = []`);
  there is no vendored, copied, or generated third-party source in the distributed artifact.
- **Clean-room implementation.** Prior art (see `docs/research/`) was studied, not copied; no external
  schema, fixture, font, or asset with incompatible terms is incorporated.
- **Dev/build tools** (pytest, mypy, ruff, hatchling, packaging, …) carry their own permissive
  licenses (MIT/BSD/PSF/Apache-2.0/MPL-2.0) and are **not** part of the runtime artifact; their
  notices remain their own and are preserved where required. `packaging` (Apache-2.0/BSD) and
  `pathspec` (MPL-2.0) are dev-only and neither modified nor redistributed.

Nothing incorporated into the repository prevents distribution under MIT. Dependencies keep their own
license obligations; no required third-party notice is removed.

### Git history

Historical commits, tags and releases are **not** rewritten (they are the record of the state at
their time). The relicense enters as an explicit decision from the v0.4 baseline; the v0.1/v0.2
final reports retain a note that the license was Apache-2.0 at those freezes.

## Consequences

- GitHub detects "MIT License"; package metadata, docs, and the site agree (gate:
  `LICENSE_CONTRADICTION = 0`, `APACHE_REFERENCE_RESIDUAL = 0` for EPISTEMOS-own references —
  third-party facts about other projects' Apache-2.0 licenses are unchanged and correct).
- Downstream users get the simplest permissive terms; no patent-grant clause (MIT has none — an
  accepted trade-off for a small library, and the owner's explicit choice).

## Rejected alternatives

- **Stay Apache-2.0** — rejected by owner decision (prefer MIT's simplicity/recognition).
- **Dual-license** — unnecessary complexity for a permissive-only project.
- **A modified/derived MIT** — rejected: only the verbatim OSI MIT text is used.
