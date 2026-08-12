# EPCTX/1 — Consumer guide

How any agent consumes EPISTEMOS context — local, REST, or MCP — with the same semantics and no
EPISTEMOS internals.

## One surface, three transports

```python
from epistemos.protocol.client import LocalContextClient, RestContextClient, McpContextClient

local = LocalContextClient(engine, principal)                 # in-process
rest  = RestContextClient("http://127.0.0.1:8000", "token")   # REST boundary
mcp   = McpContextClient(mcp_server)                          # MCP tool

doc = client.context("Datastore", intent="current")          # -> EPCTX/1 document
```

All three return an equivalent EPCTX/1 document (verified by `test_local_rest_mcp_equivalent`).

## What a well-behaved consumer does

```python
doc = client.context(query, intent="current")

# 1. Is it disputed? (never treat a disputed claim as settled fact)
if doc["disputed"]:
    handle_contradictions(doc["contradictions"])

# 2. Is it complete? (never read silence as "nothing to know")
if not doc["completeness"]["complete"]:
    note_gaps(doc["completeness"]["reasons"])            # e.g. history_collapsed

# 3. Distinguish claims from facts
for claim in doc["context"]["claims"]:
    assert claim["object_type"] == "claim"               # belief_state / accepted_state carry the truth-status

# 4. Trace provenance when needed
why = doc["provenance"]["items"]

# 5. Temporal: "now" vs "then"
if doc["temporal"]["has_historical_state"]:
    ...

# 6. Expand a collapsed group if you need the folded members (experimental)
for h in doc["expansion"]["handles"]:
    members = client.expand(h["handle"])                 # re-authorized live
```

## Reference harness

`GenericAgentHarness` is a reference consumer built only on the client — it requests context,
inspects completeness, reads contradictions, consumes provenance, and follows expansion, with a
pluggable (offline) model. Use it as a template; it is not a product.

```python
from epistemos.protocol import GenericAgentHarness
report = GenericAgentHarness(local).consult("Revenue", intent="contradiction")
# report["disputed"], report["complete"], report["has_provenance"], report["answer"]
```

## Forward compatibility

Ignore optional fields you do not recognize (see [VERSIONING](VERSIONING.md)). Rely only on the
required set. A newer `EPCTX/1.x` producer will only add optional fields.

## Rendering to a model

If your model wants text, `render(doc, style)` produces a fenced, data-only CONTEXT block; use
`render_prompt(system, doc, user)` for a full prompt with hard role boundaries. Never let evidence
text act as instruction — the renderer already fences it (see [RENDERING](RENDERING.md)).
