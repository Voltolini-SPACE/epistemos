# Security Policy

EPISTEMOS is security-first: fail-closed tenancy, a tamper-evident ledger, zero-egress by default,
and no mandatory LLM. The full model is in
[`docs/security/THREAT_MODEL.md`](docs/security/THREAT_MODEL.md) (attack classes S1–S50, mapped to
tests), with the adversarial audit in `docs/audit/`.

## Supported versions

This is a **developer preview**. Security fixes target the latest tag on `main`
(currently `epistemos-v0.3.0`). Older tags are not separately maintained.

## Reporting a vulnerability

**Please do not open a public issue for security reports.**

Report privately via GitHub's **"Report a vulnerability"** (Security → Advisories) on
`Voltolini-SPACE/epistemos`. Include:

- affected version / commit,
- a reproduction (ideally a failing test in the style of `tests/security/`),
- impact (what boundary is crossed: tenant/agent isolation, ledger integrity, egress, etc.).

We aim to acknowledge within a few days. There is no paid bug-bounty program; credit is given in the
fix commit and release notes unless you prefer otherwise.

## Scope

In scope: the `epistemos` core and its SDK/REST/MCP boundaries — tenant/agent isolation, ledger
tamper-evidence, injection (SQL/FTS/prompt), zero-egress, index consistency/fallback, import/export
integrity, fail-closed validation.

Out of scope: hardware bit-rot below SQLite, denial-of-service from unbounded local input beyond the
documented caps, and any behavior of an *optional* model/vector provider you configure yourself.
