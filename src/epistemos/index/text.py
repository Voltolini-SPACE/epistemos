"""Shared text helpers + a SAFE FTS query normalizer (EPISTEMOS-02).

The tokenizer is byte-for-byte the v0.1 tokenizer (`[A-Za-z0-9]+`, lowercased) so the legacy
scan retriever and the FTS index agree on what a "term" is (semantic parity). The FTS content
is indexed with SQLite's `ascii` tokenizer, whose token boundaries match this regex.

:func:`fts_match_query` turns arbitrary user text into a **safe** FTS5 MATCH string: each token
is emitted as a double-quoted literal, so FTS5 operators (`AND`/`OR`/`NOT`/`NEAR`/`*`/`(`/`"`/`:`
column filters) in user input are treated as *data*, never as query syntax. This closes FTS
injection at the boundary.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["tokens", "object_text", "fts_match_query", "MAX_QUERY_TERMS"]

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

# Cap the number of distinct query terms fed to FTS to bound token-explosion / deep-boolean
# query cost (a 1 MiB query could otherwise become a 100k-term OR). The first N terms are used.
MAX_QUERY_TERMS = 64


def tokens(text: str | None) -> list[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text)]


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
    else:
        parts = [obj.get("id")]
    return " ".join(str(p) for p in parts if p)


def fts_match_query(text: str | None) -> str | None:
    """Build a safe FTS5 MATCH string from user text, or ``None`` if there are no terms.

    Tokens are re-quoted as literals and OR-combined (any-term recall, matching the v0.1
    scorer). User-supplied FTS operators cannot escape the quoting.
    """
    toks = tokens(text)
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
