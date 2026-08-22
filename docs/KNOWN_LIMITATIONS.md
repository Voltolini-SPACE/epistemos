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

Since v0.8 there **is** a path from raw text to knowledge: `Engine.compile_document` /
`epistemos compile` reads a document deterministically and proposes candidate claims, each pinned
to the character span it came from. It needs no model and makes no network call. What it does not
do:

- **It is not an NER and does not pretend to be one.** The built-in rules read unambiguous
  structure (`Key: Value`, front matter, definition lists, table rows) plus a small, explicitly
  enumerated set of relational sentence patterns. Free-flowing prose that states a fact in a shape
  no rule covers yields **nothing** — silently. Recall on unstructured narrative is low by design,
  and low recall here looks identical to "the document said nothing".
- **English-shaped sentence rules.** The structural rules are language-neutral; the relational
  patterns (`works at`, `reports to`, `is a`, `is in`, `owns`) are not. Other languages need
  custom rules — the registry is public and takes them, but none ship.
- **Editing a document re-proposes its unchanged lines.** Provenance points at a specific document
  version, so a changed file is a new document and every extraction from it is new. Two documents
  asserting the same thing are deliberately *two* claims: in an evidence-first system, two
  independent sources are stronger than one, and collapsing them would destroy that. The cost is
  duplication when a file is edited repeatedly. Attaching new evidence to an existing claim
  instead — one claim, many sources — is the better model and is not implemented.
- **Nothing it produces is true.** Every compiled claim is `PROPOSED`. Belief stays derived at read
  time and acceptance stays governed. This is a feature, but it means compilation alone does not
  populate `current()` — you still need review and governance to turn candidates into knowledge.

For anything beyond what the rules can read with certainty, a `ModelProvider` may supply
`extract_triples`. The default `NullModelProvider` refuses it, and nothing in the core requires it.

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
