# EPISTEMOS Interface System v1

An extension of the EPISTEMOS brandbook for the operational interface. Premium, dark, technical,
high information density. Every value is a **token** (`web/styles.css`); screens never hard-code
colors or spacing.

## Foundations

- **Brand:** indigo `#8B93FF` / `#4A50C4`, amber `#F0B54A`, ink `#0B0E17`. Dark-first (light tokens
  ship via `:root[data-theme="light"]` but the product commits to dark).
- **Type:** Geist (UI), Fraunces (display), JetBrains Mono (data/ids/timestamps). A modular scale
  `--fs-0…--fs-7`.
- **Space / radius / elevation:** `--s-1…--s-7`, `--r-1…--r-round`, `--e-1…--e-3` + a brand `--glow`.

## Semantic language (never color alone — §32)

Every status carries an **icon + text**, not just a hue:

| domain | states |
|--------|--------|
| belief | ✓ ACCEPTED · ⚠ DISPUTED · ↑ SUPPORTED · ○ PROPOSED · ✕ REJECTED · ⊘ RETRACTED/SUPERSEDED |
| verdict | ✓ confirm · ⚠ dispute · ✕ reject · – abstain · ? request_evidence |
| visibility | ▪ PRIVATE / TEAM / ORGANIZATION / COMMUNITY / PUBLIC (swatch + label) |
| data state | LIVE · SNAPSHOT · STALE · UNAVAILABLE |
| health | HEALTHY · DEGRADED (dot + word) |
| connection | LIVE · RECONNECTING · OFFLINE · STALE |

## Graph color language

entity indigo · fact cyan · claim amber · evidence green · review violet · source slate · decision
coral · agent teal · space deep-indigo. Edge colors: SUPPORTS green, CONTRADICTS red (thicker),
WEAKENS coral, DERIVED_FROM indigo, SUPERSEDES violet, REFERENCES slate, REVIEWED_BY violet.

## Components (`web/`)

AppShell · Sidebar · CommandPalette · SearchBox · GraphCanvas · GraphNode/Edge · Inspector · Timeline ·
ActivityFeed · MetricCard · Sparkline/Bars/Donut · ClaimCard · EvidenceCard · ReviewRow · BeliefBadge ·
VisibilityBadge · AgentBadge · SourceBadge · HealthIndicator · ConnectionIndicator · EmptyState ·
ErrorState · Skeleton · TimeTravel banner.

See `MOTION.md` for the motion language and `ACCESSIBILITY.md` for the a11y contract.
