"""Markdown-vault rules — Obsidian-flavoured markup, read with the same discipline as the builtins.

A personal knowledge vault states most of its facts in three shapes the builtin rules cannot see:
YAML front matter (a fenced ``---`` block of keys about *the note*), wikilinks (``[[Target]]``,
the edge that makes the vault a graph), and tags (``#projeto/se7en``). This module reads exactly
those three, deterministically, stdlib-only, and nothing more:

* **Front matter is parsed as a declared subset, not as YAML.** Scalars, quoted scalars, inline
  lists and block lists compile; nested mappings, anchors, multiline scalars are *declined, not
  guessed* — an unreadable value yields no claim rather than a wrong one. An unterminated fence is
  not front matter at all.
* **The builtins are masked out of regions they misread.** ``kv_line`` firing inside the front
  matter fence or inside a fenced code block produces confident nonsense (`"Key: Value"` in a shell
  snippet is not a fact about the note). Masking replaces those regions with spaces of the same
  length before delegating, so every span still indexes the *original* text and evidence quotes
  stay exact.
* **Everything stays a PROPOSED claim.** Nothing here asserts truth; the graph edge a wikilink
  proposes is reviewable evidence like any other extraction.

The English relational builtins remain in the set unmasked: on a Portuguese vault they simply
never fire, and silence costs nothing. Portuguese sentence patterns are a separate mission with
their own precision evidence.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

from . import BUILTIN_RULES, Extraction, PatternRule, Rule, Span, _normalize_predicate

__all__ = [
    "MARKDOWN_RULES",
    "FrontmatterRule",
    "MaskedRule",
    "TAG",
    "WIKILINK",
    "code_fence_spans",
    "frontmatter_bounds",
]

# ---------------------------------------------------------------------------
# Region detection.

#: A fenced code block: ``` or ~~~ opening line through the matching closing line (or EOF —
#: an unterminated fence swallows the rest of the document, which is how renderers read it too).
_CODE_FENCE = re.compile(
    r"^(?P<fence>```|~~~).*?$(?:.*?^(?P=fence)[ \t]*$|.*\Z)", re.MULTILINE | re.DOTALL
)
#: Inline code span: `...` on one line. Masked for the markup rules so `[[x]]` in code is not
#: an edge.
_INLINE_CODE = re.compile(r"`[^`\n]+`")


def frontmatter_bounds(text: str) -> Span | None:
    """The front-matter region including both fences, or ``None`` when there is none.

    Only a document that *starts* with ``---`` has front matter, and only when a closing
    ``---``/``...`` line exists. Anything else — including an unterminated fence — is body text.
    """
    if not text.startswith("---\n") and text != "---":
        return None
    close = re.compile(r"^(?:---|\.\.\.)[ \t]*$", re.MULTILINE)
    m = close.search(text, 4)
    if m is None:
        return None
    return Span(0, m.end())


def code_fence_spans(text: str) -> tuple[Span, ...]:
    """Spans of fenced code blocks and inline code, in document order."""
    spans = [Span(m.start(), m.end()) for m in _CODE_FENCE.finditer(text)]
    spans.extend(
        Span(m.start(), m.end())
        for m in _INLINE_CODE.finditer(text)
        if not any(s.start <= m.start() < s.end for s in spans)
    )
    spans.sort()
    return tuple(spans)


def _mask(text: str, spans: Sequence[Span]) -> str:
    """Replace each span with spaces of the same length — offsets into the original survive."""
    if not spans:
        return text
    out = list(text)
    for span in spans:
        out[span.start:span.end] = " " * (span.end - span.start)
    return "".join(out)


# ---------------------------------------------------------------------------
# Front matter — a declared YAML subset, parsed line by line, fail-closed.

_FM_KEY = re.compile(r"^(?P<key>[A-Za-zÀ-ÖØ-öø-ÿ_][\w .'/-]{0,79}?)[ \t]*:[ \t]*(?P<rest>.*)$")
_FM_LIST_ITEM = re.compile(r"^[ \t]+-[ \t]+(?P<item>\S.*?)[ \t]*$")
#: A value that is exactly one wikilink unwraps to its target: `up: "[[HOME]]"` names HOME.
_FM_WIKILINK_VALUE = re.compile(
    r"^\[\[(?P<target>[^\[\]|#\n]+?)(?:#[^\[\]|\n]*)?(?:\|[^\[\]\n]*)?\]\]$"
)


def _fm_scalar(raw: str) -> str | None:
    """One scalar value, or ``None`` when the subset declines it (nested/anchor/multiline/empty)."""
    value = raw.strip()
    if not value:
        return None
    if value[0] in "&*|>{":  # anchor, alias, multiline scalar, flow mapping — declined
        return None
    if (value[0] == value[-1] and value[0] in "'\"") and len(value) >= 2:
        value = value[1:-1].strip()
    if not value:
        return None
    unwrapped = _FM_WIKILINK_VALUE.match(value)
    if unwrapped is not None:
        value = unwrapped.group("target").strip()
    return value or None


@dataclass(frozen=True, slots=True)
class FrontmatterRule:
    """Reads the front-matter fence as key/value claims about the note.

    Each value — and each *item* of a list value — gets its own sub-span, so list items never
    collide in overlap resolution and every claim quotes exactly the value it came from.
    ``tags``/``tag`` keys emit ``tagged_with`` so front-matter tags and body ``#tags`` are the
    same predicate.
    """

    name: str = "frontmatter"
    confidence: float = 1.0

    def apply(self, text: str, subject: str) -> Iterator[Extraction]:
        region = frontmatter_bounds(text)
        if region is None:
            return
        body = text[region.start:region.end]
        lines = body.split("\n")
        offset = region.start
        current_key: str | None = None
        current_key_line_had_value = False
        for line in lines:
            line_start = offset
            offset += len(line) + 1
            if line.strip() in ("---", "...", ""):
                current_key = None
                continue
            keyed = _FM_KEY.match(line)
            if keyed is not None:
                key = keyed.group("key").strip()
                rest = keyed.group("rest")
                current_key = key
                current_key_line_had_value = bool(rest.strip())
                predicate = self._predicate(key)
                if not predicate:
                    current_key = None
                    continue
                stripped = rest.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    # Inline list: every item is its own claim with its own sub-span.
                    inner_start = line_start + line.find("[") + 1
                    yield from self._items(stripped[1:-1], inner_start, subject, predicate)
                    current_key = None
                elif stripped:
                    value = _fm_scalar(rest)
                    if value is not None:
                        vstart = line_start + line.rfind(rest)
                        yield Extraction(
                            subject=subject, predicate=predicate, object=value,
                            rule=self.name, span=Span(vstart, line_start + len(line)),
                            confidence=self.confidence,
                        )
                    current_key = None
                continue
            item = _FM_LIST_ITEM.match(line)
            # A block list only belongs to a key whose own line carried no value.
            if item is not None and current_key is not None and not current_key_line_had_value:
                predicate = self._predicate(current_key)
                if predicate:
                    value = _fm_scalar(item.group("item"))
                    if value is not None:
                        istart = line_start + line.find("- ") + 2
                        yield Extraction(
                            subject=subject, predicate=predicate, object=value,
                            rule=self.name, span=Span(istart, line_start + len(line)),
                            confidence=self.confidence,
                        )
                continue
            # Any other shape — nested mapping, continuation, garbage — is declined silently.
            current_key = None

    def _items(
        self, inner: str, inner_start: int, subject: str, predicate: str
    ) -> Iterator[Extraction]:
        pos = 0
        for part in inner.split(","):
            start = inner_start + pos
            pos += len(part) + 1
            value = _fm_scalar(part)
            if value is None:
                continue
            lead = len(part) - len(part.lstrip())
            yield Extraction(
                subject=subject, predicate=predicate, object=value,
                rule=self.name, span=Span(start + lead, start + len(part.rstrip())),
                confidence=self.confidence,
            )

    @staticmethod
    def _predicate(key: str) -> str:
        slug = _normalize_predicate(key)
        return "tagged_with" if slug in ("tags", "tag") else slug


# ---------------------------------------------------------------------------
# Body markup rules — both are the fixed-predicate document-subject shape.

#: ``[[Target]]`` / ``[[Target|alias]]`` / ``[[Target#heading]]`` -> (note, links_to, Target).
#: The lookbehind excludes embeds (``![[img]]``): an embed renders content, it does not cite it.
_WIKILINK_RE = re.compile(
    r"(?<!!)\[\[(?P<object>[^\[\]|#\n]+?)(?:#[^\[\]|\n]*)?(?:\|[^\[\]\n]*)?\]\]"
)
WIKILINK = PatternRule(
    name="wikilink", pattern=_WIKILINK_RE, predicate="links_to",
    document_subject=True, confidence=1.0,
)

#: ``#tag`` / ``#nested/tag`` -> (note, tagged_with, tag). Letter-first (Unicode) excludes
#: ``# Heading`` and ``#123``; the lookbehind excludes URL fragments and mid-word hits.
_TAG_RE = re.compile(r"(?<![\w/&#])#(?P<object>[^\W\d_][\w/-]*)", re.UNICODE)
TAG = PatternRule(
    name="tag", pattern=_TAG_RE, predicate="tagged_with",
    document_subject=True, confidence=1.0,
)


# ---------------------------------------------------------------------------
# Masking wrapper.


@dataclass(frozen=True, slots=True)
class MaskedRule:
    """Delegates to ``rule`` with declared regions blanked out.

    Masked regions are replaced by spaces of identical length, so every span the inner rule
    reports still indexes the original text — evidence quotes stay exact.
    """

    rule: Rule
    regions: Callable[[str], Sequence[Span]]

    @property
    def name(self) -> str:
        return self.rule.name

    @property
    def confidence(self) -> float:
        return self.rule.confidence

    def apply(self, text: str, subject: str) -> Iterator[Extraction]:
        yield from self.rule.apply(_mask(text, self.regions(text)), subject)


def _fenced_regions(text: str) -> Sequence[Span]:
    """Front matter + code: regions where *body* rules must not read."""
    spans = list(code_fence_spans(text))
    fm = frontmatter_bounds(text)
    if fm is not None:
        spans.append(fm)
    return spans


#: The vault rule set: front matter owned by its parser, markup rules blind to front matter and
#: code, builtins blind to the same regions. Deterministic, overlap-resolved by the Compiler.
MARKDOWN_RULES: tuple[Rule, ...] = (
    FrontmatterRule(),
    MaskedRule(WIKILINK, _fenced_regions),
    MaskedRule(TAG, _fenced_regions),
    *(MaskedRule(rule, _fenced_regions) for rule in BUILTIN_RULES),
)
