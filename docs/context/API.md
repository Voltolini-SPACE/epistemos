# Context Envelope — API

## `engine.context(...)`

```python
env = engine.context(
    principal,               # Principal — authority; never taken from a payload
    query=None,              # str | None — the retrieval query
    *,
    compact=True,            # True → EPCTX/1 envelope; False → raw search results
    at_tx=None,              # as-of transaction time (bitemporal); None = now
    intent=None,             # optional intent hint: current|historical|change|decision|contradiction
) -> dict
```

- `compact=True` → the `EPCTX/1` dict (see [ENVELOPE_SCHEMA.md](ENVELOPE_SCHEMA.md)).
- `compact=False` → `{"format": "raw", "results": [...]}` — unchanged `engine.search` output.
- `intent=None` lets the engine classify the query (conservatively). Pass `intent` when the caller
  knows it (an agent usually does) — a confident `current` intent is what unlocks history collapse.

The envelope is **additive**. `engine.search` is unchanged and remains the primitive; `context` is a
convenience transform over it.

### Example

```python
from epistemos import Engine, Principal
from epistemos.storage import MemoryStore

eng = Engine(MemoryStore())
p = Principal(tenant="acme", agent="analyst", namespace="kb", capabilities={"knowledge.read"})

f = eng.assert_fact(p, subject="Datastore", predicate="is", object="mongo")
f = eng.supersede(p, f.id, new={"object": "postgres"}, reason="migration")

env = eng.context(p, "Datastore", intent="current")
# env["items"] → the current fact inline
# env["collapsed_groups"] → the superseded 'mongo' version, folded but reachable
# env["context_incomplete"] is True with reason "history_collapsed"
```

## Builder (direct)

```python
from epistemos.context import ContextEnvelopeBuilder, EnvelopeConfig

env = ContextEnvelopeBuilder(engine).build(
    principal, query, config=EnvelopeConfig(), at_tx=None, intent="current",
)
env.to_dict()          # EPCTX/1
env.reachable_ids()    # delivered ∪ every collapsed id
env.object_ids()       # delivered ids only
```

## `EnvelopeConfig`

| field | default | status |
|---|---|---|
| `pin_contradictions` | `True` | stable |
| `collapse_redundancy` | `True` | stable |
| `top_n` | `12` | stable |
| `budget_pack` | `False` | **experimental** |
| `token_budget` | `None` | **experimental** |
| `continuation` | `False` | **experimental** |

Experimental knobs are off by default and can never drop a pinned contradiction or a critical item;
when they do drop anything, the envelope declares `context_incomplete`.

## REST / MCP

Not enabled in v0.6. If added later, the principal is bound **server-side**; tenant / principal /
capabilities are never accepted from the request payload (see [SECURITY.md](SECURITY.md)). The SDK
transform (`engine.context`) is the supported surface for now.
