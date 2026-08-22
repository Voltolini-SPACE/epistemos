"""Markdown-vault rules: what they read, what they refuse, and that they never lose the builtins.

The vault-facing properties under test: front matter is a *declared subset* (declined, not
guessed), wikilinks and tags are graph edges about the note, masking keeps builtins out of
regions they misread while every span still quotes the original bytes, and the whole set stays
byte-reproducible.
"""

from __future__ import annotations

from epistemos.ingest import BUILTIN_RULES, compile_text
from epistemos.ingest.markdown import (
    MARKDOWN_RULES,
    code_fence_spans,
    frontmatter_bounds,
)

NOTE = """---
status: ativo
owner: "Léo Voltolini"
tags: [missão, se7en/pay]
aliases:
  - Nota Principal
  - Hub
up: "[[HOME]]"
---

# Painel

Contexto em [[EPISTEMOS]] e [[NOMOS|o orquestrador]], seção [[Brandbook#Cores]].
Embed ![[logo.png]] não é citação. Tag no corpo: #missão e #infra/mac.

```bash
Owner: fake-do-código
export NOMOS_HOME=~/.nomos  # [[não-é-link]] #não-é-tag
```

Fora do código, `Inline: code` também não conta.

| Ambiente | Estado |
|---|---|
| producao | ativo |
"""


def _triples(text: str, subject: str = "nota") -> set[tuple[str, str, str | None]]:
    return {
        (e.subject, e.predicate, e.object)
        for e in compile_text(text, subject=subject, rules=MARKDOWN_RULES)
    }


# -- front matter ------------------------------------------------------------


def test_frontmatter_scalars_quoted_lists_and_wikilink_values():
    got = _triples(NOTE)
    assert ("nota", "status", "ativo") in got
    assert ("nota", "owner", "Léo Voltolini") in got                # quotes stripped
    assert ("nota", "tagged_with", "missão") in got                 # inline list, per item
    assert ("nota", "tagged_with", "se7en/pay") in got
    assert ("nota", "aliases", "Nota Principal") in got             # block list, per item
    assert ("nota", "aliases", "Hub") in got
    assert ("nota", "up", "HOME") in got                            # whole-value wikilink unwrapped


def test_frontmatter_kv_line_never_fires_inside_the_fence():
    for e in compile_text(NOTE, subject="nota", rules=MARKDOWN_RULES):
        if e.rule == "kv_line":
            assert e.span.start > frontmatter_bounds(NOTE).end  # type: ignore[union-attr]


def test_unterminated_fence_is_not_frontmatter():
    text = "---\nstatus: ativo\ncorpo sem fecho"
    assert frontmatter_bounds(text) is None
    assert ("nota", "status", "ativo") in _triples(text)  # read by kv_line as body, not frontmatter


def test_nested_mappings_anchors_and_multiline_scalars_are_declined():
    text = "---\nmeta:\n  nested: deep\nref: *alias\nbody: |\n  multiline\n---\n"
    preds = {p for (_, p, _) in _triples(text)}
    assert "nested" not in preds
    assert "ref" not in preds
    assert "body" not in preds


def test_frontmatter_only_at_document_start():
    text = "corpo\n---\nstatus: ativo\n---\n"
    assert frontmatter_bounds(text) is None


# -- wikilinks ---------------------------------------------------------------


def test_wikilink_plain_alias_and_heading_forms_name_only_the_target():
    got = _triples(NOTE)
    assert ("nota", "links_to", "EPISTEMOS") in got
    assert ("nota", "links_to", "NOMOS") in got        # alias stripped
    assert ("nota", "links_to", "Brandbook") in got    # heading ref stripped


def test_embeds_and_code_wikilinks_are_not_edges():
    targets = {o for (_, p, o) in _triples(NOTE) if p == "links_to"}
    assert "logo.png" not in targets       # ![[embed]]
    assert "não-é-link" not in targets     # inside code fence


def test_wikilink_with_diacritics():
    assert ("nota", "links_to", "Sessões") in _triples("veja [[Sessões]]")


# -- tags --------------------------------------------------------------------


def test_body_tags_including_nested_and_accented():
    got = _triples(NOTE)
    assert ("nota", "tagged_with", "missão") in got
    assert ("nota", "tagged_with", "infra/mac") in got


def test_headings_numbers_urls_and_code_are_not_tags():
    text = "# Título\nissue #123 e https://x.y/#frag\n`#nem-em-code`\n#sim"
    tags = {o for (_, p, o) in _triples(text) if p == "tagged_with"}
    assert tags == {"sim"}


# -- masking & spans ---------------------------------------------------------


def test_builtins_are_masked_out_of_code_fences():
    objects = {o for (_, p, o) in _triples(NOTE)}
    assert "fake-do-código" not in objects
    assert not any(o and "Inline" in str(o) for o in objects)


def test_masked_spans_still_quote_the_original_text():
    for e in compile_text(NOTE, subject="nota", rules=MARKDOWN_RULES):
        if e.rule == "wikilink":
            assert e.span.text(NOTE).startswith("[[")


def test_table_rows_still_compile_outside_masked_regions():
    assert ("producao", "row_value", "ativo") in _triples(NOTE)


def test_code_fence_spans_cover_fenced_and_inline_code():
    spans = code_fence_spans(NOTE)
    assert any("fake-do-código" in s.text(NOTE) for s in spans)
    assert any("Inline: code" in s.text(NOTE) for s in spans)


# -- determinism & control ---------------------------------------------------


def test_markdown_compilation_is_byte_reproducible():
    runs = [
        tuple(
            (e.subject, e.predicate, e.object, e.rule, e.span)
            for e in compile_text(NOTE, subject="nota", rules=MARKDOWN_RULES)
        )
        for _ in range(5)
    ]
    assert len(set(runs)) == 1


def test_control_builtins_alone_see_no_graph_and_misread_the_fence():
    """The experiment that justifies this module: the old pipeline proposes zero edges, zero
    tags, and *does* fire inside code fences — the new set adds recall and removes that noise."""
    old = {
        (e.predicate, e.object)
        for e in compile_text(NOTE, subject="nota", rules=BUILTIN_RULES)
    }
    assert not any(p == "links_to" for p, _ in old)
    assert not any(p == "tagged_with" for p, _ in old)
    assert ("owner", "fake-do-código") in old  # the misread the mask kills


def test_control_no_body_recall_is_lost():
    """Every builtin extraction from outside the masked regions survives in the new set."""
    fence = frontmatter_bounds(NOTE)
    code = code_fence_spans(NOTE)

    def masked(start: int) -> bool:
        if fence is not None and start < fence.end:
            return True
        return any(s.start <= start < s.end for s in code)

    old_kept = {
        (e.subject, e.predicate, e.object)
        for e in compile_text(NOTE, subject="nota", rules=BUILTIN_RULES)
        if not masked(e.span.start)
    }
    new = _triples(NOTE)
    assert old_kept <= new
