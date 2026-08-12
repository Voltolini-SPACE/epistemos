# EPCTX/1 — Temporal contract

EPISTEMOS is bitemporal. EPCTX exposes that without asking the consumer to do timestamp math (§9).

**Per object** (`context.*[].temporal`):

```jsonc
{ "valid_from", "valid_to", "transaction_from", "transaction_to", "is_current": true }
```

- **valid time** (`valid_from` / `valid_to`) — when the statement was true in the world.
- **transaction time** (`transaction_from` / `transaction_to`) — when the system believed it.
- **is_current** — the single boolean a consumer branches on: is this the currently-believed state or
  a superseded/historical one.

**Per document** (`temporal`):

```jsonc
{ "as_of": null, "has_current_state": true, "has_historical_state": false }
```

- `as_of` — the transaction-time snapshot the document was built against (`null` = now).
- `has_current_state` / `has_historical_state` — whether the document carries current and/or
  historical objects.

This lets a consumer answer **"what is believed now?"** vs **"what was believed then?"** directly:

- `engine.epctx(p, "Datastore", intent="current")` → collapses history, `has_current_state=true`.
- `engine.epctx(p, "Datastore", intent="historical")` → preserves versions; both flags true and
  each object's `is_current` distinguishes the live one from the superseded ones.
- `engine.epctx(p, "Datastore", as_of="<tx>")` → reconstructs the snapshot at that transaction time.
