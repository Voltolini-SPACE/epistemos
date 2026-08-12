# Motion language

Motion has meaning — it tells the eye that something *changed* or *related*, never decoration for its
own sake (mission §9/§23). Timings follow the mission budget.

| tier | budget | used for |
|------|--------|----------|
| micro | 100–200 ms | hover, focus, selection, buttons, menus, tooltips |
| normal | 180–350 ms | cards/panels entering, filter transitions, search results, inspector slide |
| cinematic | ≤ 600 ms | opening Brain, entering Time Travel, expanding graph clusters |

## Principles

- **Animate `transform` and `opacity`** only; avoid layout-thrashing properties.
- **New knowledge** enters the graph with a brief expanding pulse, then the layout settles and goes
  quiet. Activity-feed rows slide in on arrival. A contradiction relation can pulse briefly. Nothing
  animates forever without purpose.
- **Adaptive effects.** Ambient effects (glow, depth) are subtle and bounded; the graph uses viewport
  culling + level-of-detail so the frame budget is spent on what's visible.

## Reduced motion (gate — §26)

Under `prefers-reduced-motion: reduce`:

- a global CSS rule collapses all animation/transition durations to ~0 and stops the live-dot pulse;
- the graph settles its layout **synchronously under a time budget** and runs no ongoing animation
  loop or entrance pulses (`graph.js` checks `prefersReducedMotion()`).

Every piece of information conveyed by motion is **also** conveyed statically — belief/verdict/health
states are icon+text badges, connection state is a labeled word, new events are simply present in the
feed. Nothing is understandable only through animation.
