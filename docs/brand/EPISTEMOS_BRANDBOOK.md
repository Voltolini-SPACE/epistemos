# EPISTEMOS — Brandbook v1.0

<img src="assets/logo-horizontal.svg" alt="EPISTEMOS" width="360"/>

`BRAND_VERSION = 1.0` · Apache-2.0 · An independent product showcased on voltolini.space.

---

## 1. Brand essence
**Knowledge you can trust, through time.** EPISTEMOS is memory with a memory of itself — every fact
knows when it was true, when it was believed, and where it came from.

## 2. Mission
Give agents and runtimes a sovereign, auditable memory they own — temporal, explainable, and
traceable to its source — without surrendering it to a model, a vendor, or the cloud.

## 3. Vision
A world where AI systems reason over knowledge that is **accountable**: reconstructable at any point
in time, explainable in every retrieval, and tamper-evident by construction — portable across any
agent, runtime, or model.

## 4. Positioning
**EPISTEMOS — Sovereign Context, Memory & Provenance Infrastructure for AI Agents.**
Secondary: *Persistent temporal memory, explainable knowledge and decision lineage for any agent or
runtime.* Positioned against LLM-native memory (opaque, cloud-bound, non-deterministic) as the
deterministic, local-first, provenance-first alternative.

## 5. Product category
Context / memory / knowledge-graph / provenance **infrastructure** (not an app, not an agent, not a
database product). Peer set: agent-memory layers, temporal knowledge graphs, GraphRAG engines.

## 6. Audience
Agent developers · AI infrastructure teams · orchestration frameworks · sovereign / self-hosted AI
stacks · local-first AI systems. Technical, senior, security-aware readers.

## 7. Brand personality
Rigorous · sovereign · precise · calm · premium-technical. The engineer's engine: it does not
over-claim, it shows its evidence. Confident without hype.

## 8. Voice
Plain, exact, and evidence-led. Prefer measured claims with a number and a source over adjectives.
Name limitations openly. Speak to peers, not to marketers.

## 9. Tone
- **Do:** "100k search: 6.2 s → 34 ms (~183×), reproducible in `benchmarks/`."
- **Don't:** "blazing-fast, revolutionary AI memory." No "Palantir for AI", no "brain", no hype.
- Serious about security and sovereignty; quietly confident about performance.

## 10. Naming rules
- Product: **EPISTEMOS** (wordmark all-caps; "EPISTEMOS" in prose). Package/import: `epistemos`.
- Never "Epistemos by NOMOS" / "NOMOS EPISTEMOS". Versions: `epistemos-vX.Y.Z`.
- Greek *epistēmē* (knowledge). Pronounced eh-PIS-teh-mos.

## 11. Logo concept
A **wordmark** ("EPISTEMOS", bold, wide letter-spacing) paired with the **strata mark**. Primary
lockups: horizontal (`assets/logo-horizontal.svg`), mark-only (`assets/mark.svg` /
`assets/mark-tile.svg`), favicon (`assets/favicon.svg`).

## 12. Symbol concept
**Epistemic strata.** A vertical **provenance spine** crossed by three horizontal **temporal strata**
of different lengths, with **lineage nodes** at each crossing — the middle "now / evidence" node in
amber. It reads simultaneously as (a) stacked time-layers, (b) a lineage graph, and (c) an abstract
"E". No brain, no neural-net, no robot, no generic AI spark.

## 13. Clear space
Minimum clear space around any lockup = the height of one lineage node (the amber dot) on all sides.
For the horizontal lockup, keep at least that margin inside its containing chip.

## 14. Minimum size
- Mark: **16 px** (favicon). Horizontal lockup: **120 px** wide minimum.
- Below 24 px, use the simplified `favicon.svg` (fewer strata) rather than the full mark.

## 15. Color system
| Role | Dark (default) | Light | Notes |
|------|----------------|-------|-------|
| INK / background | `#0B0E17` | `#FBFBFD` | base surface |
| SURFACE | `#151A28` | `#FFFFFF` | cards, chips |
| TEXT | `#EAECF4` | `#12141C` | AAA on base |
| MUTED | `#98A2BD` | `#565C6E` | secondary text (AA) |
| PRIMARY (indigo) | `#8B93FF` | `#3A40B8` | links, mark, primary |
| PRIMARY-DEEP | `#4A50C4` | `#4A50C4` | buttons / mark on light |
| ACCENT (amber) | `#F0B54A` | `#B8791E` | the "now"/evidence node, highlights |
| SUCCESS / WARNING / ERROR | `#3FB984` / `#E8A13C` / `#E5605E` | same | status only |

All text pairs verified **WCAG AA or AAA** (see the brand palette check). Amber is an **accent**,
never body text. Indigo is the identity color; amber marks *evidence / the present moment*.

## 16. Typography
No font binaries and no external font fetches (reinforces zero-egress/local-first). System stacks:
- `HEADLINE_FONT`: `ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` (bold, tight tracking for display; wide tracking for the wordmark).
- `BODY_FONT`: same sans stack, regular/medium.
- `MONO_FONT`: `ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace` — for code, metrics, and the benchmark chip.

## 17. Iconography
Line icons, 2px stroke, rounded caps, on a 24px grid — echoing the strata mark (horizontal bars +
nodes). Monochrome (indigo or currentColor); amber reserved for the single "current/evidence" accent.

## 18. Grid
- Web: 12-column, max content width ~1120px, 24px gutters; 8px spacing scale.
- Mark: 48-unit artboard; spine at x=15, strata at y=13/24/35.

## 19. UI direction
Dark-first, calm, dense-but-legible. Ink surfaces, hairline borders (`#2A3350`), generous line-height,
monospace for evidence/metrics. Motion is minimal and purposeful (respect `prefers-reduced-motion`).
The feeling: an instrument, not a billboard.

## 20. Diagrams
Diagrams use the strata/lineage language: horizontal time-layers, a vertical spine, labelled nodes,
and directional lineage arrows (source → observation → fact → derived fact → decision). Indigo lines,
amber for the focal node, muted labels. Always readable in both themes and on mobile.

## 21. GitHub presentation
Avatar = `mark-tile.svg`. README leads with the horizontal lockup, a one-liner, the reproducible
benchmark, and a minimal quickstart. Topics: ai, agent-memory, knowledge-graph, context-engineering,
temporal-memory, provenance, graph-rag, mcp, local-first, ai-infrastructure, bitemporal,
decision-lineage. Social preview = `og.svg` (rasterized to PNG for upload).

## 22. Web presentation
`voltolini.space/epistemos`: dark hero with the strata field, the positioning line, two CTAs (GitHub,
Architecture), then sections (Why / What / How / Runtimes / Temporal / Provenance / Performance /
Security / Developer). Uses the color system and system fonts; no external font/CDN calls.

## 23. Social / Open Graph presentation
`og.svg` → `og.png` (1200×630): ink gradient, strata field, mark, "EPISTEMOS", positioning line, and
the benchmark chip. `og:title` = "EPISTEMOS — Sovereign Context, Memory & Provenance for AI Agents".

## 24. Do / Don't
**Do:** show numbers with sources; keep amber for evidence only; use the strata language; state
limitations; equal-weight co-branding.
**Don't:** call it "production ready" without proof; imply shipped integrations; nest EPISTEMOS under
NOMOS; use brain/robot/AI-spark clichés; reuse the NOMOS identity; stretch or recolor the mark;
put amber as body text.

## 25. Integration co-branding rules
- Describe NOMOS/Hermes/OpenClaw as **future consumers/adapters** ("designed to integrate with",
  "adapter-ready", "planned") until each integration mission ships.
- In any pairing, EPISTEMOS keeps its own mark/color and equal visual weight; never presented as a
  component of the other system. EPISTEMOS provides context/evidence; it never grants capabilities.
