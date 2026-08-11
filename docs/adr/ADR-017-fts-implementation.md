# ADR-017 — FTS implementation: SQLite FTS5, safe query, documented parity differences

**Status:** Accepted (v0.2)

## Context
The lexical index must be stdlib-first, local, zero-egress, model-free, tenant/temporal-aware and
explainable (mission §3). SQLite (already the store) ships FTS5.

## Decision
`SqliteFtsIndex` (`index/fts.py`) is an FTS5 virtual table **in the same database and connection as
the store**, with `tokenize='ascii'` (token boundaries match the v0.1 `[A-Za-z0-9]+` tokenizer).

- **Safe query.** User text is normalized (`index/text.py::fts_match_query`) into **quoted literal
  tokens** OR-combined and capped at `MAX_QUERY_TERMS`. FTS5/SQL operators in user input are treated
  as data — no FTS/SQL injection, no wildcard/deep-boolean explosion (tested).
- **Tenant/namespace at the SQL boundary.** `WHERE fts_idx MATCH ? AND tenant = ? AND namespace = ?`
  — filtering happens in SQLite, never "retrieve globally then filter in Python" (no leakage).
- **Lexical score.** FTS5 `bm25` (negative) is normalized to a `[0,1]` `lexical` component per result
  set; the domain adds exact/temporal/authority/recency exactly as before.

### Documented, ADR-approved parity differences (vs the v0.1 scan)
1. **Lexical formula:** BM25 (FTS5) vs the v0.1 TF·IDF. The `lexical` component value and fine
   ordering among purely-lexical ties differ; all non-lexical behavior is identical (parity tests).
2. **Result set for text queries:** the indexed path returns only objects matching ≥1 query term
   (standard search semantics). The v0.1 scan additionally surfaced non-matching objects with
   positive recency/authority; the indexed path drops those — intentional.
3. **Recall bound:** up to `CANDIDATE_POOL` (500) candidates are retrieved by BM25 then re-ranked by
   the full score. For very high-frequency terms this bounds recall (a deliberate perf trade-off).

## Consequences
Fast, safe, explainable text search that preserves temporal/authority/tenant semantics. Unicode
content is not tokenized (ascii tokenizer) — same as v0.1; a unicode tokenizer is a future option.

## Rejected alternatives
- **Passing raw user text to FTS5 MATCH**: injection/DoS surface; rejected (quoted literals instead).
- **A separate index database/connection**: loses transactional consistency with the store (ADR-018).
- **Keeping TF·IDF and reconstructing corpus-wide DF from FTS**: complex for no benefit; BM25 is the
  standard, better lexical score.
