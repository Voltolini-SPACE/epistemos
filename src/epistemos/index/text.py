"""Shared text helpers + a SAFE FTS query normalizer (EPISTEMOS-02; unicode mode EPISTEMOS-03).

Tokenization is a pluggable :class:`Tokenizer` so the legacy scan retriever and the FTS index
always agree on what a "term" is (semantic parity — ADR-021). Two tokenizers ship:

* :data:`ASCII` — the v0.1/v0.2 default: ``[A-Za-z0-9]+`` lowercased, matching SQLite's ``ascii``
  FTS5 tokenizer. Non-ASCII content is not tokenized (a known limitation, ADR-017).
* :data:`UNICODE` — EPISTEMOS-03 (ADR-023): unicode-aware, diacritic-folding. It tokenizes
  **through SQLite's own ``unicode61 remove_diacritics 2`` tokenizer**, so the python scan and the
  FTS index are byte-identical by construction — a pure-python approximation cannot match SQLite's
  curated fold table (Cyrillic ё stays distinct, ñ folds to n, Hangul stays composed). ``sqlite3``
  is stdlib, so this adds no third-party dependency.

:func:`fts_match_query` turns arbitrary user text into a **safe** FTS5 MATCH string: each token is
emitted as a double-quoted literal, so FTS5 operators (`AND`/`OR`/`NOT`/`NEAR`/`*`/`(`/`"`/`:`
column filters) in user input are treated as *data*, never as query syntax. This closes FTS
injection at the boundary regardless of tokenizer.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from typing import Any

__all__ = [
    "tokens",
    "object_text",
    "fts_match_query",
    "MAX_QUERY_TERMS",
    "Tokenizer",
    "AsciiTokenizer",
    "SqliteUnicodeTokenizer",
    "PluralNormalisingTokenizer",
    "ASCII",
    "UNICODE",
    "PLURAL",
    "get_tokenizer",
]

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

# Cap the number of distinct query terms fed to FTS to bound token-explosion / deep-boolean
# query cost (a 1 MiB query could otherwise become a 100k-term OR). The first N terms are used.
MAX_QUERY_TERMS = 64


class Tokenizer:
    """Turns text into a list of lowercased terms. ``name`` labels the persisted choice;
    ``fts_tokenize`` is the SQLite FTS5 ``tokenize=`` option the index must use to agree."""

    name: str = "ascii"
    fts_tokenize: str = "ascii"

    def tokens(self, text: str | None) -> list[str]:  # pragma: no cover - abstract
        raise NotImplementedError

    def normalize_text(self, text: str) -> str:
        """The representation that is *persisted* into the lexical index.

        The FTS5 ``tokenize=`` option is fixed when the virtual table is created, so a
        transformation SQLite cannot express (plural folding, alias expansion) cannot be pushed
        down into the tokenizer. Pushing it *up* instead — normalising the text before it is
        indexed — keeps both sides in agreement: SQLite tokenizes already-normalised content, and
        a query normalised the same way produces terms that match it.

        The default is identity, so a tokenizer that only changes how text is split (rather than
        what it says) needs no migration and no override. E-2 measured what happens without this:
        the scan path and the index path answered the same question differently, which breaks
        RETRIEVAL_SEMANTIC_PARITY (ADR-021).
        """
        return text


class AsciiTokenizer(Tokenizer):
    name = "ascii"
    fts_tokenize = "ascii"

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        return [t.lower() for t in _TOKEN_RE.findall(text)]


class SqliteUnicodeTokenizer(Tokenizer):
    """Unicode-aware tokenizer that defers to SQLite so the scan and index agree exactly.

    Uses a private in-memory FTS5 table + ``fts5vocab`` to read back the exact terms SQLite would
    index. Order is reconstructed from the raw text (fts5vocab is unordered) so TF·IDF and phrase
    positions in the scan match a natural reading. Thread-safe via an internal lock.
    """

    name = "unicode"
    fts_tokenize = "unicode61 remove_diacritics 2"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            conn = sqlite3.connect(":memory:", check_same_thread=False)
            conn.execute(
                f"CREATE VIRTUAL TABLE tok USING fts5(c, tokenize='{self.fts_tokenize}')"
            )
            # 'instance' vocab yields one row per token occurrence with its offset, so we read
            # the exact terms, multiplicity and order SQLite itself produces — no python
            # re-implementation of unicode61's fold table, which cannot be matched exactly.
            conn.execute("CREATE VIRTUAL TABLE tok_i USING fts5vocab(tok, 'instance')")
            self._conn = conn
        return self._conn

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        with self._lock:
            conn = self._connection()
            conn.execute("INSERT INTO tok(rowid, c) VALUES (1, ?)", (text,))
            try:
                rows = conn.execute("SELECT term FROM tok_i ORDER BY offset").fetchall()
            finally:
                conn.execute("DELETE FROM tok WHERE rowid = 1")
        return [r[0] for r in rows]


class PluralNormalisingTokenizer(AsciiTokenizer):
    """ASCII tokenisation plus a conservative English singulariser (E-2 candidate B2).

    Measured on the 520-document E-1 corpus: morphology nDCG@10 0.056 -> 0.520, global nDCG@10
    +0.051, **no growth in indexed terms**, +1.6 ms p50, and no regression in any category. It is
    deliberately not a stemmer — it removes a trailing plural marker and nothing else, so every
    rule is one a reviewer can read and refute.

    Opt-in. Selecting it re-creates and rebuilds the index, because the persisted representation
    changes (``normalize_text`` is no longer identity).
    """

    name = "plural"
    fts_tokenize = "ascii"

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        return [_singular(t.lower()) for t in _TOKEN_RE.findall(text)]

    def normalize_text(self, text: str) -> str:
        """Rewrite the text into its indexed form: same words, singularised.

        Non-word characters are preserved so the stored content stays readable and diffable — the
        index is evidence too, and evidence you cannot read is worth less.
        """
        return _TOKEN_RE.sub(lambda m: _singular(m.group(0).lower()), text)


#: Words whose trailing "s" is not a plural marker. Small and explicit on purpose: a list a
#: reviewer can check beats a lexicon nobody audits.
_KEEP_S = frozenset({
    "as", "is", "us", "gas", "bus", "analysis", "basis", "status", "access", "process",
    "class", "cross", "less", "loss", "miss", "pass", "press", "always", "https", "this",
    "was", "has", "its", "yes", "news", "series", "species",
})


def _singular(word: str) -> str:
    """Conservative English singulariser. Never changes a word it is unsure about."""
    if len(word) <= 3 or word in _KEEP_S or not word.endswith("s"):
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"                       # policies -> policy
    if word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]                             # approaches -> approach
    if word.endswith("ss"):
        return word
    return word[:-1]                                 # retentions -> retention


ASCII = AsciiTokenizer()
PLURAL = PluralNormalisingTokenizer()
UNICODE = SqliteUnicodeTokenizer()

_BY_NAME: dict[str, Tokenizer] = {ASCII.name: ASCII, UNICODE.name: UNICODE,
                                  PLURAL.name: PLURAL}


def get_tokenizer(name: str | Tokenizer) -> Tokenizer:
    """Resolve a tokenizer by name (``"ascii"``/``"unicode"``) or pass one through."""
    if isinstance(name, Tokenizer):
        return name
    try:
        return _BY_NAME[name]
    except KeyError:
        raise ValueError(
            f"unknown tokenizer {name!r} (known: {sorted(_BY_NAME)})"
        ) from None


def tokens(text: str | None, tokenizer: Tokenizer = ASCII) -> list[str]:
    """Tokenize with the given tokenizer (default: ASCII, the v0.1/v0.2 behaviour)."""
    return tokenizer.tokens(text)


def object_text(obj: dict[str, Any]) -> str:
    """The searchable text for an object (identical to the v0.1 scorer's view)."""
    kind = obj.get("kind")
    if kind == "fact":
        parts = [obj.get("subject"), obj.get("predicate"), obj.get("object")]
    elif kind == "entity":
        parts = [obj.get("name"), obj.get("entity_type"), *obj.get("aliases", [])]
    elif kind == "document":
        parts = [obj.get("title"), obj.get("text")]
    elif kind == "decision":
        parts = [obj.get("statement"), obj.get("outcome")]
    elif kind == "episode":
        parts = [obj.get("summary")]
    elif kind == "observation":
        parts = [obj.get("text")]
    elif kind == "claim":  # EPISTEMOS-05: claims are searchable, marked as CLAIM by the caller
        parts = [obj.get("subject"), obj.get("predicate"), obj.get("object")]
    elif kind == "evidence":
        parts = [obj.get("title"), obj.get("uri"), obj.get("origin")]
    elif kind == "review":
        parts = [obj.get("rationale")]
    else:
        parts = [obj.get("id")]
    return " ".join(str(p) for p in parts if p)


def fts_match_query(text: str | None, tokenizer: Tokenizer = ASCII) -> str | None:
    """Build a safe FTS5 MATCH string from user text, or ``None`` if there are no terms.

    Tokens are re-quoted as literals and OR-combined (any-term recall, matching the v0.1
    scorer). User-supplied FTS operators cannot escape the quoting. The tokenizer must be the
    same one the index was built with, or the quoted literals will not match indexed terms.
    """
    toks = tokenizer.tokens(text)
    if not toks:
        return None
    # de-duplicate (preserve order) and cap to bound query cost; tokens are [A-Za-z0-9]+ so they
    # contain no quote/operator chars, but quote defensively anyway
    seen: dict[str, None] = {}
    for t in toks:
        seen.setdefault(t, None)
        if len(seen) >= MAX_QUERY_TERMS:
            break
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in seen)
