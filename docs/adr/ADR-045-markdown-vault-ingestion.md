# ADR-045 — Markdown-vault ingestion: `epistemos ingest`, markdown rules, inherited tokenizer

**Status:** ACCEPTED (E-5)

## Context

The only ingestion surface was `epistemos compile FILE` — one file per invocation, builtin rules
only. A personal knowledge vault (Obsidian-style) states most of its facts in shapes those rules
cannot see: YAML front matter, `[[wikilinks]]`, `#tags` — and its bulk facts in Portuguese, which
the default ascii tokenizer cannot retrieve (`Sessões` was unmatchable without diacritic folding).
Worse, `kv_line` fired *inside* fenced code blocks and front-matter fences, proposing confident
nonsense with evidence.

## Decision

1. **`epistemos ingest DIR`** — deterministic sorted walk, real-globstar include/exclude globs,
   per-file fail-closed errors (never an aborted run), idempotent by construction: document
   identity is the existing content hash (`Engine.document_content_hash`, one definition), path
   identity is `metadata.vault_path`, and a changed file becomes a new document recording
   `metadata.supersedes`. Batch dedupe reuses `compile_document(known_keys=...)` — one claims
   scan per run, not per file.
2. **`MARKDOWN_RULES`** (`epistemos.ingest.markdown`) — `FrontmatterRule` parses a *declared YAML
   subset* (scalars, quoted scalars, inline/block lists; nested mappings, anchors and multiline
   scalars are declined, not guessed); `WIKILINK` -> `(note, links_to, Target)`; `TAG` ->
   `(note, tagged_with, tag)`; builtins are masked out of front-matter and code regions with
   same-length space masking, so spans still quote the original bytes.
3. **Tokenizer default inherits the store** — `Engine.open(tokenizer=None)` reads the recorded
   `fts_tokenizer` instead of forcing ascii; a caller that merely opens a database (`verify`,
   `serve`) can no longer rebuild its index by omitting a flag. A NEW database created by
   `ingest` defaults to `unicode`.

## Consequences

- Re-running `ingest` on an unchanged vault creates zero claims (proven by integration test and
  against the real vault). Edited files still re-propose their claims — the documented
  KNOWN_LIMITATIONS position stands; `supersedes` is the hook a future evidence-merge needs.
- English relational builtins stay in the set unmasked: on Portuguese text they never fire.
  Portuguese sentence patterns are future work requiring their own precision evidence.
- `Engine.open` semantics changed: opening an existing non-ascii store without an explicit
  tokenizer now KEEPS its representation (previously: silent rebuild to ascii). Explicit names
  still migrate.

## Rejected alternatives

- **PyYAML** — violates zero runtime dependencies; the subset parser declines what it cannot
  read, which is the module's philosophy.
- **`--tokenizer` flags on every subcommand as the fix** — plumbing a footgun through the CLI
  instead of removing it; the stored representation is the authority (the ADR-023 thesis).
- **Gating the English relational rules** — a flag with no benefit; silence is free.
- **`fnmatch` for globs** — translates `**` exactly like `*`, silently skipping walk-root files;
  caught by the integration test, pinned by regression.
