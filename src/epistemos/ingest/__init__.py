"""Deterministic ingestion — raw text to *candidate claims*, with no model in the loop.

Every other system in this space puts an LLM on the write path: text goes in, "memories" come
out, and those memories are written as if they were true. That is non-deterministic, it cannot be
replayed, and it launders a guess into the record.

This module takes the opposite position, and it is the reason it can exist inside a zero-egress,
stdlib-only core:

* **It never produces truth.** A compiled extraction becomes a `Claim` in `PROPOSED` state plus a
  piece of `Evidence` pointing at the exact character span it came from. Belief stays derived at
  read time; acceptance stays governed. Nothing here can promote itself into accepted knowledge.
* **It is deterministic.** The same bytes always yield the same extractions, in the same order,
  with the same ids for the same span. Compiling twice changes nothing (idempotence), and a
  reviewer can re-run the compiler to reproduce exactly what the system saw.
* **It is explainable.** Every extraction names the rule that produced it and carries the span
  offsets, so "why does the system have this claim?" is answered with a quotation, not a vibe.
* **It is conservative by construction.** The built-in rules read *unambiguous* structure —
  key/value lines, front matter, definition lists, tables — plus a small, explicitly enumerated set
  of relational sentence patterns. There is no statistical NER here and there is no attempt to
  fake one. What the rules cannot read with certainty, they leave alone.

A `ModelProvider` may still be used for enrichment on top of this (`extract_triples`), but it is
never required: the default `NullModelProvider` refuses, and the compiler is fully useful with no
model at all.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

__all__ = [
    "BUILTIN_RULES",
    "CompilationResult",
    "Compiler",
    "Extraction",
    "PatternRule",
    "Rule",
    "Span",
    "compile_text",
]

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps ingest free of a runtime core import
    from ..claims import Claim


@dataclass(frozen=True, slots=True)
class CompilationResult:
    """What one `Engine.compile_document` call did.

    ``skipped`` holds the deterministic keys of extractions that were already present — a second
    compilation of an unchanged document produces an empty ``claims`` and a full ``skipped``.
    """

    document: str
    claims: tuple[Claim, ...]
    skipped: tuple[str, ...]
    by_rule: dict[str, int]

    @property
    def created(self) -> int:
        return len(self.claims)

    def __len__(self) -> int:
        return len(self.claims)

# Values longer than this are almost never a clean fact; the rules decline rather than guess.
_MAX_VALUE = 200
# A subject/object made only of punctuation or digits is noise, not an entity.
_MEANINGFUL = re.compile(r"[^\W\d_]", re.UNICODE)


@dataclass(frozen=True, slots=True, order=True)
class Span:
    """A half-open character range `[start, end)` into the source text."""

    start: int
    end: int

    def text(self, source: str) -> str:
        return source[self.start:self.end]


@dataclass(frozen=True, slots=True)
class Extraction:
    """One candidate claim, traceable to the span that produced it.

    ``confidence`` is *not* a probability. It is the rule's declared reliability: structural rules
    reading unambiguous syntax score higher than sentence patterns, which can misread. It seeds the
    claim's confidence; it never decides belief.
    """

    subject: str
    predicate: str
    object: str | None
    rule: str
    span: Span
    confidence: float = 1.0

    def sort_key(self) -> tuple[int, int, str, str, str]:
        """Total order, so a compilation is byte-reproducible regardless of rule order."""
        return (self.span.start, self.span.end, self.rule, self.subject, self.predicate)


@runtime_checkable
class Rule(Protocol):
    """A named, deterministic reader over the whole document text.

    ``subject`` is the document-level subject (its title). Rules that read document-scoped syntax —
    `Key: Value` front matter describes *the document*, not the key — use it; rules that read a
    relation between two named things inside a sentence ignore it.
    """

    # Declared read-only (via property) rather than as plain attributes: a plain attribute in a
    # Protocol demands a *settable* one, which would exclude every frozen dataclass rule —
    # including the built-ins, which are frozen precisely so a rule set cannot mutate underfoot.
    @property
    def name(self) -> str: ...

    @property
    def confidence(self) -> float: ...

    def apply(self, text: str, subject: str) -> Iterable[Extraction]: ...


def _clean(value: str) -> str:
    """Trim surrounding whitespace, markdown emphasis and trailing sentence punctuation."""
    value = value.strip()
    value = value.strip("*_`")
    value = value.rstrip(".,;:")
    return value.strip()


def _usable_subject(value: str) -> bool:
    """A subject names an entity, so it must contain a letter — `2.1` is not a thing."""
    return bool(value) and len(value) <= _MAX_VALUE and _MEANINGFUL.search(value) is not None


def _usable_value(value: str) -> bool:
    """An object may legitimately be purely numeric (`Port: 8787`, `Version: 2.1`)."""
    return bool(value) and len(value) <= _MAX_VALUE


@dataclass(frozen=True, slots=True)
class PatternRule:
    """A rule driven by one regex with named groups ``key``/``subject``/``object``.

    The pattern must be anchored enough that a match is unambiguous. Three shapes are supported:

    * **Document-scoped** (``document_subject=True``, no ``predicate``): the match's ``key`` group
      becomes the predicate and the subject is the document itself. `Owner: Alice` in a runbook is
      a statement *about the runbook*, so it compiles to ``(<doc title>, owner, Alice)``. Reading
      it as ``(Owner, …, Alice)`` would invent an entity called "Owner".
    * **Document-scoped with a fixed predicate** (``document_subject=True`` and ``predicate``):
      the subject is the document and the predicate is the rule's own. Markup that *relates the
      document to a named thing* — a `[[wikilink]]`, a `#tag` — has no ``key`` group to read; the
      rule itself is the predicate: ``(<doc title>, links_to, Target)``.
    * **Relational**: ``subject`` and ``object`` both come from the text and ``predicate`` is fixed
      by the rule — `Alice works at Acme` -> ``(Alice, works_at, Acme)``.
    """

    name: str
    pattern: re.Pattern[str]
    predicate: str = ""
    document_subject: bool = False
    confidence: float = 1.0

    def apply(self, text: str, subject: str) -> Iterator[Extraction]:
        for m in self.pattern.finditer(text):
            groups = m.groupdict()
            raw_object = groups.get("object")
            obj = _clean(raw_object) if raw_object is not None else None

            if self.document_subject:
                subj = subject
                # Lazy on purpose: a fixed-predicate rule has no ``key`` group to read.
                predicate = self.predicate or _normalize_predicate(m.group("key"))
            else:
                subj = _clean(m.group("subject"))
                predicate = self.predicate

            if not _usable_subject(subj) or not predicate:
                continue
            if obj is not None and not _usable_value(obj):
                continue
            yield Extraction(
                subject=subj,
                predicate=predicate,
                object=obj,
                rule=self.name,
                span=Span(m.start(), m.end()),
                confidence=self.confidence,
            )


def _normalize_predicate(raw: str) -> str:
    """`Reports To` / `reports-to` / `Reports  to` -> `reports_to`. Deterministic, lossless enough
    to be readable, and stable across documents so the same key always yields the same predicate."""
    slug = re.sub(r"[^\w]+", "_", raw.strip().lower(), flags=re.UNICODE).strip("_")
    return slug[:80]


# ---------------------------------------------------------------------------
# Built-in rules.
#
# Ordering here is presentation only — `Compiler` sorts by span so the output is deterministic
# regardless of the order rules are registered in.

#: `Key: Value` on its own line — the single most common shape in notes, runbooks and front
#: matter. Unambiguous, so it scores 1.0. The subject is the *document* (bound at compile time),
#: which is why this rule emits the key as the predicate and the value as the object.
_KV_LINE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?P<key>[A-Za-z][\w .'/-]{0,79}?)[ \t]*:[ \t]*"
    r"(?P<object>[^\n]{1,200}?)[ \t]*$",
    re.MULTILINE,
)

#: Markdown definition list: `Term` then a line starting with `: definition`. The term is a real
#: entity here (unlike a front-matter key), so this one is relational.
_DEF_LIST = re.compile(
    r"^[ \t]*(?P<subject>[A-Za-z][\w .'/-]{0,79})[ \t]*\n[ \t]*:[ \t]+(?P<object>[^\n]{1,200})$",
    re.MULTILINE,
)

#: Two-column markdown table row: `| Subject | Object |`. Separator rows (`|---|---|`) are excluded
#: by requiring the first cell to start with a letter, and the *header* row is excluded by the
#: lookahead: a row immediately followed by a separator names the columns, it does not state a fact.
_TABLE_ROW = re.compile(
    r"^[ \t]*\|[ \t]*(?P<subject>[^\W\d_][^|\n]{0,79}?)[ \t]*\|[ \t]*"
    r"(?P<object>[^|\n]{1,200}?)[ \t]*\|[ \t]*$"
    r"(?!\n[ \t]*\|[\s:|-]*\|)",
    re.MULTILINE,
)

# -- relational sentence patterns -------------------------------------------
# Deliberately few, deliberately anchored, deliberately not an NER. Each one is a shape that is
# hard to misread; anything looser would manufacture claims the document does not make.

# No `.` inside a subject token: allowing it lets a subject swallow a sentence boundary
# ("Acme. Alice Martins" read as one name), which invents an entity and then out-ranks the
# correct extraction during overlap resolution.
_SUBJ = r"(?P<subject>[A-Z][\w'-]*(?:[ ][A-Z][\w'-]*){0,4})"
_OBJ = r"(?P<object>[^.\n]{1,120}?)"

_WORKS_AT = re.compile(rf"\b{_SUBJ}\s+works?\s+(?:at|for)\s+{_OBJ}(?=[.\n,;]|$)")
_IS_A = re.compile(rf"\b{_SUBJ}\s+is\s+(?:an?|the)\s+{_OBJ}(?=[.\n,;]|$)")
_LOCATED_IN = re.compile(rf"\b{_SUBJ}\s+is\s+(?:located\s+)?in\s+{_OBJ}(?=[.\n,;]|$)")
_REPORTS_TO = re.compile(rf"\b{_SUBJ}\s+reports?\s+to\s+{_OBJ}(?=[.\n,;]|$)")
_OWNS = re.compile(rf"\b{_SUBJ}\s+owns\s+{_OBJ}(?=[.\n,;]|$)")

#: The built-in registry. Structural rules score 1.0 (they read syntax, not language); sentence
#: patterns score 0.7 because English is ambiguous and a pattern can misread a clause.
BUILTIN_RULES: tuple[Rule, ...] = (
    PatternRule(name="kv_line", pattern=_KV_LINE, document_subject=True, confidence=1.0),
    PatternRule(name="definition_list", pattern=_DEF_LIST, predicate="defined_as", confidence=1.0),
    PatternRule(name="table_row", pattern=_TABLE_ROW, predicate="row_value", confidence=1.0),
    PatternRule(name="works_at", pattern=_WORKS_AT, predicate="works_at", confidence=0.7),
    PatternRule(name="is_a", pattern=_IS_A, predicate="is_a", confidence=0.7),
    PatternRule(name="located_in", pattern=_LOCATED_IN, predicate="located_in", confidence=0.7),
    PatternRule(name="reports_to", pattern=_REPORTS_TO, predicate="reports_to", confidence=0.7),
    PatternRule(name="owns", pattern=_OWNS, predicate="owns", confidence=0.7),
)


@dataclass(slots=True)
class Compiler:
    """Runs a rule set over text and returns a deterministic, de-overlapped extraction list."""

    rules: tuple[Rule, ...] = field(default=BUILTIN_RULES)
    #: When two rules claim overlapping spans, keep the higher-confidence one. A structural read
    #: of `Owner: Alice` should win over a sentence pattern that also matched inside it.
    resolve_overlaps: bool = True

    def compile(self, text: str, *, subject: str = "document") -> list[Extraction]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        found: list[Extraction] = []
        for rule in self.rules:
            found.extend(rule.apply(text, subject))
        found.sort(key=lambda e: e.sort_key())
        if not self.resolve_overlaps:
            return found
        return _drop_overlaps(found)


def _drop_overlaps(items: Sequence[Extraction]) -> list[Extraction]:
    """Keep the strongest extraction per overlapping region, breaking ties deterministically.

    Ties are broken by the sort key (span, then rule name), never by rule registration order, so
    the result does not depend on how the registry was built.
    """
    kept: list[Extraction] = []
    for item in items:
        clash = None
        for i, existing in enumerate(kept):
            if item.span.start < existing.span.end and existing.span.start < item.span.end:
                clash = i
                break
        if clash is None:
            kept.append(item)
            continue
        # Only a *strictly* more confident reading of the same region replaces the incumbent;
        # equal confidence keeps the earlier one, which the sort already made deterministic.
        if item.confidence > kept[clash].confidence:
            kept[clash] = item
    return kept


def compile_text(
    text: str, *, subject: str = "document", rules: Sequence[Rule] | None = None
) -> list[Extraction]:
    """Convenience wrapper: compile ``text`` with the built-in rules (or a supplied set)."""
    compiler = Compiler(rules=tuple(rules) if rules is not None else BUILTIN_RULES)
    return compiler.compile(text, subject=subject)
