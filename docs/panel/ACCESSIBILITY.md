# Accessibility

Accessibility is a **gate**, not a finish. Target: WCAG 2.1 AA, keyboard-first.

## Keyboard

- The whole panel is navigable without a mouse: the command palette (`⌘K`) reaches every view and every
  searchable object; results are arrow-navigable, Enter opens, Esc closes.
- The **graph** canvas is focusable (`role="application"`, descriptive `aria-label`) and driven by the
  keyboard: arrows move the selection between nodes, Enter opens the selected node, `+`/`-` zoom, `f`
  fit.
- Dialogs (inspector, palette) trap focus and close on Escape.

## Not color alone (§32)

Belief, verdict, visibility, health and connection states are always **icon + text**, never a hue only:
`✓ ACCEPTED`, `⚠ DISPUTED`, `✕ REJECT`, `▪ PRIVATE`, `HEALTHY`, `LIVE`. Colour is reinforcement, not the
signal.

## Graph alternative

The graph is visual **and** has a navigable non-visual representation: the "≣ list" view renders the same
authorized nodes and their relations as a keyboard-focusable table, each row opening the inspector — so
graph information is never reachable only by sight or pointer.

## Structure & contrast

Semantic landmarks (`nav`, `main`, `header`, `role="dialog"/"listbox"/"option"`), visible focus rings
(`:focus-visible`), and a dark palette tuned for AA contrast on text and controls. `main` is focused on
route change so screen-reader users land on new content.

## Reduced motion

`prefers-reduced-motion` is honoured everywhere (see `MOTION.md`): all information carried by animation
is also available statically.

## Known gaps / next validation

An automated axe-core sweep and a full screen-reader pass across every screen are the recommended next
validation; the contract above is implemented and manually verified, and the graph's alternative view
plus keyboard model close the highest-risk gaps.
