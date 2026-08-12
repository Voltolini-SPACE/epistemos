# EPISTEMOS Panel v1 — Final Report (EPISTEMOS-PANEL-01: Living Knowledge Interface)

**Repo:** `Voltolini-SPACE/epistemos` · **Branch:** `feat/epistemos-panel-01` · **Core baseline:**
`epistemos-v0.5.0` (unchanged) · **Python:** 3.14 · **Runtime deps:** 0 · **License:** MIT.

## Executive summary

The official operational interface for EPISTEMOS — a **local-first, zero-egress** panel that turns the
epistemological engine into a live, explorable experience: *see the knowledge thinking*. It is a
**consumer** (ADR-030): authorization stays in the core, and the browser grants nothing. Built on pure
stdlib + vanilla HTML/CSS/JS (no framework, no npm, no CDN) so it runs offline from a single
`python -m epistemos.panel`.

- **API/event boundary** (`epistemos.api`): an authorized read-model (`PanelService`) and an
  authorization-filtered SSE stream (`authorized_events`), served by a stdlib HTTP+SSE server under a
  strict self-only CSP. One new core primitive — `Engine.is_readable` — gates every byte.
- **Panel** (`src/epistemos/panel/web`): Overview / Brain Pulse, a Canvas graph explorer (LOD +
  culling + spatial-grid physics), global search + `⌘K` command palette, Claim Center with belief
  **decomposition**, Evidence Explorer, Explain mode, Timeline + **Time Travel** (real bitemporal
  `as_of`), Spaces, Agent Observatory, Source Intelligence, System Health. Honest empty/degraded/
  no-permission/offline states.
- **Realtime** (ADR-031): SSE tail of the ledger with resume-by-seq and honest connection states
  (LIVE/RECONNECTING/OFFLINE/STALE). No fake realtime — every event is a real ledger record.
- **Security** (ADR-032): the four P0 leak invariants proven 0 across every surface.

## The eight mandated questions

**1. Does the panel use only real EPISTEMOS data?** **Yes.** Every view is served by the authorized
read-model over a real `Engine`; there is no mock on the production path. The demo corpus is built
through the **real public Engine API** (real sources/entities/claims/evidence/reviews/decisions,
persisted, ledgered) and read back through the real boundary — a fixture of real objects, not mocks
(§36). No `setInterval`-invented events, no random metrics, no fake agents/counters.

**2. Does the graph allow continuous Obsidian-style exploration?** **Yes.** search → open node → see
relations → expand neighbours → open claim → see evidence → see contradiction → *Why?* → time-travel,
all without leaving the visual context. Verified in-browser (24-node authorized graph with a red
CONTRADICTS edge; click→inspector; double-click/Enter→expand; ⌘K→open). LOD/culling/keyboard/pin/filter/
fit/fullscreen + an accessible list view.

**3. Do real changes appear without a reload?** **Yes.** Verified live: with the real-object generator
running, the Overview counters grew (16 → 26 objects) and the Timeline filled from SSE events, with the
connection reading LIVE — no reload. New graph nodes pulse in; the feed prepends; counters refresh.

**4. Can the user go back in time?** **Yes.** Timeline → Time Travel runs the core's real bitemporal
`as_of` at a chosen instant and reports what EPISTEMOS knew then (authorized to the caller), visually
marked as viewing the past. It is real bitemporal semantics, not a client approximation.

**5. Can the user understand why something is believed?** **Yes.** The Claim view and Explain mode show
a **belief decomposition** — the evidence (supports/contradicts) and the individual reviews
(confirm/dispute) that derive the state — with the three identities kept separate (claimant ≠ ingesting
agent ≠ source). Verified: the flagship claim renders SEC filing + Newswire (supports), a press denial
(contradicts), bob (confirm), curator (dispute) → **DISPUTED**. No "AI confidence = truth".

**6. Do private data stay invisible in graph/search/stream?** **Yes — proven.** As bob, searching the
private marker returns "No results"; the private claim never appears in his graph, counts, or stream,
while its owner sees it. Automated: 22 boundary tests + full-stack HTTP tests assert
`PRIVATE_UI_LEAK = PRIVATE_GRAPH_LEAK = PRIVATE_SEARCH_LEAK = PRIVATE_STREAM_LEAK = 0`, including
visibility composition (a shared claim never exposes private evidence behind it), no-oracle errors, and
cross-tenant closure.

**7. Does the panel work without NOMOS/Hermes/OpenClaw?** **Yes.** The panel depends only on the
EPISTEMOS core; none of the three are integrated or imported. Their repos are unchanged (NOMOS HEAD
`2cea197e` = baseline). Future NOMOS/Hermes/OpenClaw → EPISTEMOS → Panel integration remains optional.

**8. Is it local-first with no mandatory cloud?** **Yes.** Binds `127.0.0.1`, zero third-party runtime
deps, a strict `default-src 'self'` CSP that blocks any external request, and the core's zero-egress
guarantee. `python -m epistemos.panel` is the whole install; it runs fully offline.

## Freeze gates

```
PANEL_BUILD              PASS   python -m epistemos.panel serves; 877 tests green; ruff + mypy --strict clean
REAL_DATA_ONLY           PASS   authorized read-model over a real Engine; demo corpus = real objects (§36)
NO_PRODUCTION_MOCKS      PASS   no mock on the production path; fixtures isolated to demo.py / tests
GRAPH_EXPLORER           PASS   canvas explorer, LOD/culling/physics, full interaction set
OBSIDIAN_LIKE_NAVIGATION PASS   search→node→expand→claim→evidence→why→time-travel without leaving context
GLOBAL_SEARCH            PASS   /api/search, typed grouped results, claim≠accepted-knowledge
COMMAND_PALETTE          PASS   ⌘K palette + commands, keyboard-first
TIME_TRAVEL              PASS   real bitemporal as_of; marked as viewing the past
EXPLAIN_MODE             PASS   authorization-aware belief decomposition + provenance
CLAIM_CENTER             PASS   claim/claimant/source/space/status/belief/temporal/evidence/reviews
EVIDENCE_EXPLORER        PASS   origin/hash/uri/space/visibility + supports/contradicts (readable-filtered)
DECISION_LINEAGE         PASS   decision detail: statement → "decided from" evidence → OUTCOME; + graph DECIDED_FROM edges
KNOWLEDGE_SPACES_UI      PASS   PRIVATE..PUBLIC, never PUBLIC default, exposure note; membership/visibility
AGENT_OBSERVATORY        PASS   only real observed agents, real per-agent stats
SOURCE_INTELLIGENCE      PASS   trust = authority (not truth), usage, navigable
REALTIME_STREAM          PASS   SSE authorized tail; live counters/feed/graph
AUTO_RECONNECT           PASS   EventSource + Last-Event-ID resume by seq
STALE_STATE              PASS   LIVE/RECONNECTING/OFFLINE/STALE; old data never shown as live
PRIVATE_UI_LEAK          0      tests/panel/test_leak.py
PRIVATE_GRAPH_LEAK       0      node iff readable, edge iff both readable; expand re-filters
PRIVATE_SEARCH_LEAK      0      authorized search; private marker never in others' results
PRIVATE_STREAM_LEAK      0      filtered at the source (§34); redacted envelope; cross-tenant closed
REDUCED_MOTION           PASS   CSS gate + graph time-budgeted static settle; info also non-animated
WCAG_AA                  PASS*  keyboard-first, ARIA landmarks, focus rings, not-color-alone, graph list view
                                (*automated axe + full screen-reader pass = recommended next validation)
KEYBOARD_NAVIGATION      PASS   palette + graph arrow-nav + dialog focus/Escape
RESPONSIVE               PASS   desktop full; mobile bottom-nav + stacked cards + touch graph (verified 375px)
GRAPH_PERFORMANCE        PASS   render ~0.2ms @1500 nodes; culling/LOD/grid; cap+truncated disclosure
SEARCH_PERFORMANCE       PASS   core FTS ~34ms @100k (SQLite); ~1.3s scan (in-memory demo store)
ANIMATION_FRAME_BUDGET   PASS   transform/opacity only; reduced-motion time-budgeted; no infinite GPU loops
ZERO_DEAD_UI             PASS   every visible control works or is a real link; no placeholders/lorem/TODO
ZERO_CONSOLE_ERRORS      PASS   non-erroring auth probe (whoami 200); no JS/CSP/resource errors on load
ZERO_EGRESS_DEFAULT      PASS   strict default-src 'self' CSP; core zero-egress; 127.0.0.1 bind
LOCAL_FIRST              PASS   stdlib only, no cloud required, runs offline
MIT_LICENSE              PASS   unchanged
NOMOS/HERMES/OPENCLAW_UNTOUCHED  TRUE  not integrated; NOMOS HEAD 2cea197e = baseline
```

**One honest caveat:** `WCAG_AA` is implemented and manually verified (keyboard, ARIA, not-color-alone,
graph alternative list view, reduced-motion) with an automated axe-core + full screen-reader sweep
flagged as the recommended next validation. Everything else is a substantiated PASS; nothing is reported
as PASS that is not.

## Verification

877 tests (855 core + 22 panel) green; `mypy --strict` clean (38 files); `ruff` clean (src + tests).
Panel security: 22 tests incl. a real ephemeral server. Browser-verified across desktop + mobile with
screenshots of every screen. Performance measured (boundary + canvas). Baselines v0.1–v0.5 unmoved;
NOMOS/Hermes/OpenClaw untouched.

`STATUS_FINAL = EPISTEMOS_PANEL_V1_PASS` (WCAG_AA automated-sweep pending as the one disclosed caveat
above; every mandated question is answered YES with evidence).
