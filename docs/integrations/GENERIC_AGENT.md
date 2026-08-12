# Integration: Generic Agent (reference)

**Status: implemented reference.** Any agent can consume EPISTEMOS through EPCTX/1 with no EPISTEMOS
internals and no dependency on any specific framework.

## Shape

```
Agent ──(authorized request)──▶ EPISTEMOS ──(EPCTX/1)──▶ Agent ──▶ reasoning / model / action
```

EPISTEMOS supplies knowledge, memory, provenance, temporal state, contradictions, and completeness.
The agent decides how to reason, which model to use, and what to attempt. A policy engine (the
agent's, not EPISTEMOS's) decides what is allowed. EPISTEMOS never executes an action or grants a
capability.

## Minimal consumer

```python
from epistemos.protocol.client import LocalContextClient   # or Rest/Mcp
doc = LocalContextClient(engine, principal).context("Datastore", intent="current")
```

Then follow the [CONSUMER_GUIDE](../protocol/CONSUMER_GUIDE.md): check `disputed`, check
`completeness`, respect `object_type` (claim vs fact), trace `provenance`, read `temporal`, and
`expand` handles when needed.

## Reference implementation

`epistemos.protocol.GenericAgentHarness` + `FakeChatModel` (offline). See
`tests/protocol/test_renderer_harness.py` and `tools/eps09_agent_bench.py`.
