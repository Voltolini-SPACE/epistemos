# Search & command palette

`⌘K` / `Ctrl-K` (or the top-bar search box) opens a unified command palette + global search.

## Behaviour

- **Instant, typed results.** Each keystroke queries `/api/search` (the core's candidate-boundary-first
  retrieval) and mixes in matching **commands** (Open Brain, Show Claims, Go to Timeline, …). Results
  are grouped by type (CLAIM, EVIDENCE, ENTITY, SOURCE, DECISION, FACT).
- **Keyboard-first.** ↑/↓ navigate, ↵ opens (a result opens its inspector; a command runs), Esc closes.
- **Typed, honest rendering.** A result shows its kind and human label; a **Claim is never silently
  presented as accepted knowledge** — belief is a separate, derived state shown in the claim view.
- **Authorized.** Search only ever returns objects you can read; each hit is enriched with its object's
  label server-side, and a hit whose object is not readable is dropped defensively. A private object's
  marker never appears in anyone else's results (`PRIVATE_SEARCH_LEAK = 0`, `SECURITY.md`).

## Filters & temporal search

The dedicated Search view supports typed filtering; temporal questions ("what did we know at T?") are
answered by the core's real bitemporal `as_of` via the Timeline → Time Travel flow (`as_of` endpoint),
never by a client-side approximation. Recent/saved searches, when enabled, are stored **locally** and
never carry sensitive knowledge off the machine.
