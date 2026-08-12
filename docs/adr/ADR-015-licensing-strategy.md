# ADR-015 — Licensing strategy: Apache-2.0, zero runtime deps, clean-room

**Status:** Superseded (license) by [ADR-027](ADR-027-mit-license.md) in v0.4 — EPISTEMOS is now
distributed under the **MIT License**. The zero-runtime-deps and clean-room decisions in this ADR
still stand; only the license choice changed. This ADR is retained as the historical record of the
original Apache-2.0 rationale.

## Context
EPISTEMOS is a new, original product (not a fork). It must be safely combinable with the intended
adapter integrations and carry a clear IP story after a large research phase.

## Decision
License **Apache-2.0** (permissive + explicit patent grant). The runtime has **zero third-party
dependencies** (stdlib only), so there is no runtime license entanglement; dev/build tools are all
permissive (MIT/BSD/PSF/Apache/MPL, dev-only). The implementation is **clean-room**: prior art was
studied for concepts, algorithms, published standards, and data models only — **no code copied**.
Any future third-party code must carry an explicitly validated license, recorded origin, demonstrated
architectural need, and correct attribution (mission §0). Evidence:
`docs/security/LICENSE_MATRIX.md`, `DEPENDENCY_INVENTORY.md`, `SBOM.md`.

## Consequences
- Strongest supply-chain posture (nothing to pin/patch at runtime).
- Apache-2.0 is compatible with the census projects' own permissive licenses, easing lawful adapter
  interop later.
- Contributors accept Apache-2.0 terms (standard inbound=outbound).

## Rejected alternatives
- **Copyleft (GPL/AGPL)**: complicates embedding EPISTEMOS as a library in other agents; rejected for
  a sovereign, embeddable engine.
- **Adding a permissive dependency for convenience** (e.g. a web framework, a graph lib): rejected in
  favor of stdlib to keep runtime deps at zero (mission §27, §39).
