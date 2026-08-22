# EPISTEMOS — Known Limitations

A product whose thesis is epistemic honesty has to publish what it cannot do. This page is that
list. It is maintained alongside [`PUBLIC_CLAIMS_AUDIT.md`](final/PUBLIC_CLAIMS_AUDIT.md): that
document states what is proven, this one states what is missing. Both are load-bearing.

Last reviewed: **2026-08-22** against core v0.7.0 / Panel v1.1.

---

## Retrieval

**Lexical only — no semantic search ships.** `VectorIndex` is a Protocol in
`src/epistemos/index/__init__.py`, and the only implementation shipped is `NullVectorIndex`.
Search is SQLite FTS5 plus the explainable scorer. Consequence: a query that paraphrases a stored
fact without sharing terms with it will not retrieve it. Every LLM-native memory system in the
field does hybrid vector + lexical retrieval and will out-recall EPISTEMOS on paraphrase.

The port exists so an embedding index can be added without touching the domain, and the scorer
already exposes named components so a vector contribution would stay explainable. It has not been
written.

## Ingestion

**Knowledge must be supplied as structured objects.** There is no path from raw text to claims.
`ModelProvider.extract_triples` is a documented optional capability, and the default
`NullModelProvider` refuses it by design — so with no model configured there is no extraction at
all, deterministic or otherwise.

Consequence: adopting EPISTEMOS means writing the ingestion layer yourself. Competing systems
accept a document or a conversation turn and build the graph for you. This is the single largest
practical barrier to trying the project.

## Scale and concurrency

- **Single node.** Storage is `MemoryStore` or `SQLiteStore`. There is no Postgres, Neo4j or any
  networked backend. The `Store` port is designed to accept one; none is written.
- **Fully synchronous.** There is no `async def` anywhere in `src/`. The REST and Panel servers are
  built on the standard library's `http.server`/`socketserver`, which serves requests serially.
  This is adequate for a local agent and a local Panel; it is not a concurrent multi-client server.
- **Benchmarked to 100k objects** on one reference machine (see
  [`benchmarks/EPISTEMOS_02_FINAL_BENCHMARK.md`](benchmarks/EPISTEMOS_02_FINAL_BENCHMARK.md)).
  Behaviour beyond that scale is not measured and is not claimed.

## Evaluation

**No score on any shared benchmark.** The field compares agent-memory systems on LoCoMo,
LongMemEval and BEAM. EPISTEMOS has published no number on any of them, so it cannot be placed on
any public comparison — in either direction. The internal benchmarks measure latency and token
shape, not recall quality against a common corpus.

## Distribution

- **Not published to PyPI.** Installation is `git clone` plus an editable install. `pip install
  epistemos` does not work today.
- The wheel builds and the console script (`epistemos`) installs, but neither has been exercised
  outside this repository's CI.

## Security scope

The security properties are real but scoped, and the scope matters:

- **Zero-egress is a property of the core**, proven by `tests/security/test_zero_egress.py`. The
  REST server, the Panel and the MCP server are network or IPC surfaces you switch on deliberately.
  Running them is not a zero-egress configuration; binding them to a non-loopback interface is your
  decision and your risk.
- **The Panel is read-only and localhost-bound**, with a strict `default-src 'self'` CSP. It has no
  built-in identity provider: tokens come from `EPISTEMOS_PANEL_TOKENS` or the demo picker.
- **The threat model excludes a compromised host.** An attacker with write access to the store file
  can be *detected* by the hash chain, but detection is not prevention, and anchors
  (`--expect-count` / `--expect-head`) must be kept somewhere the attacker cannot reach for
  truncation and full-rewrite detection to work at all.

## Integrations

`docs/integrations/` describes NOMOS, Hermes and OpenClaw adapters as **specification only**. No
integration ships and the test suite imports none of them. Treat those documents as design intent,
not as delivered capability.

## Positioning

Earlier releases of `docs/research/COMPETITOR_MATRIX.md` concluded that EPISTEMOS was the only
surveyed design combining bitemporality, determinism, hash-anchored provenance, fail-closed
tenancy, explainability and local-first operation. That census surveyed the large LLM-native
systems and missed a peer group of smaller projects making the same combination of claims. The
matrix now carries both tiers. **Do not repeat the "only system that…" formulation.**
