# ADR-023 — Opt-in unicode search: SQLite is the single tokenization authority

**Status:** Accepted (v0.3)

## Context

v0.2's FTS index and scan both tokenize with `[A-Za-z0-9]+` / SQLite `ascii`. ADR-017 disclosed the
consequence honestly: "Unicode content is not tokenized." The EPISTEMOS-03 audit measured what that
means for a non-ASCII user — searching a fact whose object is `Tóquio`:

```
search(text="Tóquio")  -> 0 results   # the ascii tokenizer splits it into t, quio
search(text="Tokyo")   -> 0 results
```

For a knowledge engine used in Portuguese, Spanish, Cyrillic, CJK or any accented text, search
silently returns nothing. That is a real defect, not just a limitation — the owner's own working
language is pt-BR.

The obvious fix (switch the tokenizer to `unicode61 remove_diacritics 2`) has a trap. The scan
retriever tokenizes in **python** and the index tokenizes in **SQLite**; ADR-021 (just established)
requires them to return the identical set. A pure-python reimplementation of `unicode61`'s fold
behaviour was measured against SQLite over 30 000 random multilingual strings:

| python approach | agreement with SQLite `unicode61 remove_diacritics 2` |
|---|---|
| `[A-Za-z0-9]+` (ascii) | n/a (different by design) |
| NFD + strip combining marks | 28% |
| NFD + strip + NFC recompose | 82% |

The residual disagreements are SQLite's curated fold table: it keeps Cyrillic `ё` distinct from `е`,
folds `ñ`→`n`, and composes Hangul in ways standard Unicode normalization does not. Matching it in
python means shipping a copy of `fts5UnicodeFold` — brittle and certain to drift across SQLite
versions. A python approximation would reintroduce exactly the scan/index divergence ADR-021 closed,
only for non-ASCII queries.

## Decision

Tokenization is a pluggable `index.text.Tokenizer`, selected at `Engine.open(tokenizer=…)`:

- **`"ascii"` (default)** — unchanged v0.1/v0.2 behaviour. Existing corpora and every existing test
  are byte-identical; ASCII-only users pay nothing.
- **`"unicode"`** — `unicode61 remove_diacritics 2`, **tokenized through SQLite itself** for both the
  index and the scan. `SqliteUnicodeTokenizer` holds a private in-memory FTS5 table and reads terms
  back via `fts5vocab(..., 'instance')`, which yields each token occurrence with its offset — so the
  scan gets SQLite's exact terms, multiplicity and order. Scan and index therefore agree **by
  construction**, not by approximation. `sqlite3` is in the standard library, so this adds no
  third-party dependency and does not weaken the clean-room / zero-deps invariant.

The FTS5 `tokenize=` option is fixed when the virtual table is created, so the chosen tokenizer name
is persisted in the store's `meta` table; opening a database with a different tokenizer drops and
rebuilds the index (`ensure_built`) — consistent with "the index is a rebuildable projection".

Injection safety is unchanged: `fts_match_query` still emits quoted literals, and the literals now
come from SQLite's own tokenizer, which cannot yield FTS operators. `MAX_QUERY_TERMS` still bounds
query cost.

## Consequences

Measured (10 000 facts, SQLite backend, same machine):

| metric | ascii | unicode |
|---|---|---|
| non-ASCII search (`Tóquio`, `café`, `Ольга`, `日本語`) | **0 hits** | **works** |
| diacritic folding (`relatorio`↔`Relatório`, `cafe`↔`CAFÉ`) | no | yes |
| build 10k facts | 1.16 s | 1.20 s (+3%) |
| per-query tokenizer cost (rare term) | ~0.02 ms | ~0.09 ms |
| scan/index parity (120-query multilingual fuzz) | n/a | **identical set, 0 divergences** |

The trade is: a small, opt-in per-query and build cost, in exchange for search that actually works
across languages, with the parity invariant preserved. Because it is opt-in and the tokenizer is
persisted-and-rebuilt, no existing behaviour changes unless a caller asks for it.

**Known boundaries (documented, not hidden):** CJK is tokenized as `unicode61` does (script runs,
not word-segmented) — there is no dictionary segmentation, so `日本語` matches as a unit, not as
`日`/`本`/`語`. No stemming, no synonyms, no stop-words. These are search-quality choices, not
correctness gaps, and are consistent with the "explainable, no hidden model" stance — a future
tokenizer can be added behind the same port.

## Rejected alternatives

- **Pure-python unicode tokenizer.** Rejected: cannot match SQLite's fold table (82% agreement
  measured), and every disagreement is a scan/index divergence — the ADR-021 bug, reborn.
- **Make `"unicode"` the default.** Rejected for this release: it changes the token set of any
  non-ASCII content in an existing database (a silent behaviour change on upgrade). Opt-in keeps the
  upgrade path boring; the default can move in a future major version with a migration note.
- **A third-party ICU/segmentation library.** Rejected: violates zero runtime dependencies for a
  quality improvement the stdlib `unicode61` already delivers.
- **Tokenize only the query in unicode, leave the index ascii.** Rejected: the index would not
  contain the folded terms, so the query still would not match — and it would desync scan and index.
