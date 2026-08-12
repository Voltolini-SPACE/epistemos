# EPISTEMOS — Brand Architecture

## Relationship model

```
                         VOLTOLINI.SPACE
                    (publisher · portfolio · showcase)
                                 │
        ┌────────────────┬───────┴────────┬──────────────────┐
        ▼                ▼                ▼                  ▼
   EPISTEMOS          NOMOS            Hermes            other projects
 (this product)   (governance)      (runtime/agent)
```

- **VOLTOLINI.SPACE** — the **publisher / portfolio / showcase**. It hosts brand presence for several
  independent products. It is *not* the owner of any product's codebase; each product has its own
  independent Git repository.
- **EPISTEMOS** — an **independent product**: knowledge / memory / provenance infrastructure. Its own
  repo (`github.com/Voltolini-SPACE/epistemos`), its own versioning, its own brand.
- **NOMOS** — a **separate governance product** (decides *what an agent may do* — a policy authority).
- **Hermes** — a **separate runtime / agent system**.
- **OpenClaw** — an **external integration / runtime**.

## Core principle

> EPISTEMOS is an **independent product**. voltolini.space is its **showcase**. NOMOS, Hermes,
> OpenClaw and other systems are **future consumers / adapters** — never architectural owners of the
> EPISTEMOS core.

EPISTEMOS records **what the system knows**; NOMOS decides **what an agent may do**. They are
complementary and orthogonal. The EPISTEMOS core imports nothing from NOMOS/Hermes/OpenClaw
(`CORE ← ADAPTER`, never the reverse), and EPISTEMOS **never grants a capability** — it provides
context, facts, history, evidence and precedent; NOMOS decides.

## Co-branding rules

- **Never** present EPISTEMOS as a dependency, submodule, or subproduct of NOMOS (or of any other
  system). No visual hierarchy that nests EPISTEMOS under NOMOS.
- When shown alongside another product, EPISTEMOS uses **its own mark and wordmark** at equal weight
  ("EPISTEMOS × NOMOS", not "NOMOS EPISTEMOS").
- Integrations are described as **"designed to integrate with" / "adapter-ready" / "planned"** until
  the corresponding integration mission ships. Never "integrated with" before that.
- EPISTEMOS may share the voltolini.space portfolio chrome (nav, footer) but keeps its **own color
  identity** (ink + indigo + amber) — it does **not** reuse the NOMOS identity.

## Naming

- Product name is **EPISTEMOS** (all caps in the wordmark; "EPISTEMOS" in running text). Never
  "Epistemos by NOMOS" or "NOMOS EPISTEMOS".
- Package / import name: `epistemos`. Repo: `Voltolini-SPACE/epistemos`. Site route: `/epistemos`.
- Versions are tagged `epistemos-vX.Y.Z` (independent of any other product's versioning).
