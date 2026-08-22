"""Deterministic ingestion: the compiler, and what it is allowed to produce.

The load-bearing property is not "it extracts things" — it is that compiling can never manufacture
truth, never vary between runs, and never lose the link back to the bytes it read.
"""

from __future__ import annotations

import re

import pytest

from epistemos.errors import NotFoundError, ValidationError
from epistemos.ingest import (
    BUILTIN_RULES,
    Compiler,
    Extraction,
    PatternRule,
    Span,
    compile_text,
)

RUNBOOK = """---
Owner: Alice Martins
Service: payments-api
Runbook version: 2.1
---

Alice Martins works at Acme. Alice Martins reports to Bruno Silva.

| Region | Endpoint |
|---|---|
| eu-west | pay-eu.internal |

Idempotency key
: A client-supplied token that makes a retry safe.
"""


def _triples(text: str, subject: str = "doc") -> set[tuple[str, str, str | None]]:
    return {(e.subject, e.predicate, e.object) for e in compile_text(text, subject=subject)}


# -- determinism -------------------------------------------------------------


def test_compilation_is_byte_reproducible():
    """Same bytes in, same extractions out — a reviewer must be able to re-derive what we saw."""
    runs = [
        tuple((e.subject, e.predicate, e.object, e.rule, e.span) for e in compile_text(RUNBOOK))
        for _ in range(5)
    ]
    assert len(set(runs)) == 1


def test_output_order_is_independent_of_rule_registration_order():
    forward = compile_text(RUNBOOK, rules=BUILTIN_RULES)
    reverse = compile_text(RUNBOOK, rules=tuple(reversed(BUILTIN_RULES)))
    assert [e.sort_key() for e in forward] == [e.sort_key() for e in reverse]


def test_non_string_input_is_refused():
    with pytest.raises(TypeError):
        compile_text(b"bytes")  # type: ignore[arg-type]


# -- the built-in rules ------------------------------------------------------


def test_key_value_lines_describe_the_document_not_the_key():
    """`Owner: Alice` in a runbook is a statement about the runbook. Reading it as an entity
    called "Owner" would invent something the document never mentions."""
    got = _triples("Owner: Alice Martins\n", subject="Runbook")
    assert ("Runbook", "owner", "Alice Martins") in got
    assert not any(subject == "Owner" for subject, _, _ in got)


def test_key_is_normalized_to_a_stable_predicate():
    assert ("D", "reports_to", "Bruno") in _triples("Reports To:  Bruno\n", subject="D")
    assert ("D", "reports_to", "Bruno") in _triples("reports-to: Bruno\n", subject="D")


def test_relational_sentence_patterns():
    got = _triples(RUNBOOK)
    assert ("Alice Martins", "works_at", "Acme") in got
    assert ("Alice Martins", "reports_to", "Bruno Silva") in got


def test_definition_list_and_table_rows():
    got = _triples(RUNBOOK)
    assert ("eu-west", "row_value", "pay-eu.internal") in got
    assert any(s == "Idempotency key" and p == "defined_as" for s, p, _ in got)


def test_table_header_and_separator_rows_are_not_claims():
    """`| Region | Endpoint |` names columns; it does not assert that Region *is* Endpoint."""
    got = _triples(RUNBOOK)
    assert ("Region", "row_value", "Endpoint") not in got
    assert not any("---" in (o or "") for _, _, o in got)


# -- conservatism: what the rules must refuse to invent -----------------------


def test_a_subject_never_crosses_a_sentence_boundary():
    """Regression: an over-permissive subject token read "Acme. Alice Martins" as one name,
    inventing an entity and then out-ranking the correct extraction during overlap resolution."""
    got = compile_text("Alice Martins works at Acme. Alice Martins reports to Bruno Silva.")
    assert all("." not in e.subject for e in got)
    assert {(e.subject, e.predicate) for e in got} == {
        ("Alice Martins", "works_at"),
        ("Alice Martins", "reports_to"),
    }


def test_numeric_values_are_kept_but_numeric_subjects_are_not():
    assert ("D", "port", "8787") in _triples("Port: 8787\n", subject="D")
    assert ("D", "runbook_version", "2.1") in _triples("Runbook version: 2.1\n", subject="D")
    # A bare number on the left of a colon is not an entity worth a claim.
    assert not any(s == "2024" for s, _, _ in _triples("2024: a good year\n", subject="D"))


def test_oversized_values_are_declined_rather_than_truncated():
    huge = "Owner: " + ("x" * 500) + "\n"
    assert _triples(huge, subject="D") == set()


def test_prose_without_a_recognized_shape_yields_nothing():
    """The compiler is not an NER. Text it cannot read with certainty must produce no claims."""
    prose = (
        "We had a long discussion yesterday and the general feeling in the room was that "
        "things might improve, although nobody was willing to commit to anything specific."
    )
    assert compile_text(prose) == []


# -- extensibility -----------------------------------------------------------


def test_a_custom_rule_can_be_supplied():
    rule = PatternRule(
        name="ticket",
        pattern=re.compile(r"\b(?P<subject>[A-Z]+-\d+)\s+is\s+(?P<object>open|closed)\b"),
        predicate="ticket_state",
        confidence=0.9,
    )
    got = compile_text("PAY-42 is open", rules=(rule,))
    assert [(e.subject, e.predicate, e.object, e.rule) for e in got] == [
        ("PAY-42", "ticket_state", "open", "ticket")
    ]


def test_overlap_resolution_prefers_the_higher_confidence_reading():
    weak = PatternRule(name="weak", pattern=re.compile(r"(?P<subject>A+)(?P<object>B+)"),
                       predicate="p", confidence=0.2)
    strong = PatternRule(name="strong", pattern=re.compile(r"(?P<subject>A+)(?P<object>B+)"),
                         predicate="p", confidence=0.9)
    got = Compiler(rules=(weak, strong)).compile("AAABBB")
    assert [e.rule for e in got] == ["strong"]


def test_overlaps_can_be_kept_when_explicitly_requested():
    weak = PatternRule(name="weak", pattern=re.compile(r"(?P<subject>A+)(?P<object>B+)"),
                       predicate="p", confidence=0.2)
    strong = PatternRule(name="strong", pattern=re.compile(r"(?P<subject>A+)(?P<object>B+)"),
                         predicate="p", confidence=0.9)
    got = Compiler(rules=(weak, strong), resolve_overlaps=False).compile("AAABBB")
    assert sorted(e.rule for e in got) == ["strong", "weak"]


def test_span_quotes_the_source_exactly():
    text = "prefix Alice Martins works at Acme. suffix"
    (item,) = [e for e in compile_text(text) if e.rule == "works_at"]
    assert item.span.text(text) == "Alice Martins works at Acme"
    assert Span(item.span.start, item.span.end).text(text) == "Alice Martins works at Acme"


# -- Engine boundary ---------------------------------------------------------


def _doc(engine, ctx, text=RUNBOOK, title="Payments API runbook"):
    return engine.ingest_document(ctx, title=title, text=text)


def test_compiling_produces_candidate_claims_never_accepted_truth(engine, ctx):
    """The whole thesis of this module: ingestion proposes, governance disposes."""
    doc = _doc(engine, ctx)
    result = engine.compile_document(ctx, document=doc.id)

    assert result.created > 0
    for claim in result.claims:
        assert engine.belief(ctx, claim.id)["state"] == "proposed"
    # Nothing was promoted into believed, valid, current knowledge.
    assert engine.current(ctx, subject="Payments API runbook", predicate="owner") is None
    assert engine.current(ctx, subject="Alice Martins", predicate="works_at") is None


def test_every_claim_is_traceable_to_the_span_that_produced_it(engine, ctx):
    doc = _doc(engine, ctx)
    result = engine.compile_document(ctx, document=doc.id)

    evidence = list(engine.store.objects(ctx.tenant, ctx.namespace, "evidence"))
    assert len(evidence) == result.created
    for ev in evidence:
        meta = ev["metadata"]
        assert ev["evidence_kind"] == "document"
        assert ev["origin"] == doc.id
        # The quote must be the literal source text at the recorded offsets.
        assert meta["quote"] == RUNBOOK[meta["span_start"]:meta["span_end"]]
        assert meta["compiler_rule"] in {r.name for r in BUILTIN_RULES}

    for claim in result.claims:
        assert claim.metadata["compiled_from"] == doc.id
        assert claim.metadata["compiler_rule"] in {r.name for r in BUILTIN_RULES}


def test_recompiling_an_unchanged_document_creates_nothing(engine, ctx):
    doc = _doc(engine, ctx)
    first = engine.compile_document(ctx, document=doc.id)
    second = engine.compile_document(ctx, document=doc.id)

    assert first.created > 0
    assert second.created == 0
    assert len(second.skipped) == first.created
    claims = list(engine.store.objects(ctx.tenant, ctx.namespace, "claim"))
    assert len(claims) == first.created


def test_a_different_document_with_the_same_text_compiles_on_its_own(engine, ctx):
    """Dedupe is per (document, content) — two documents that happen to agree are still two."""
    a = _doc(engine, ctx, text="Owner: Alice\n", title="A")
    b = _doc(engine, ctx, text="Owner: Alice\n", title="B")
    assert engine.compile_document(ctx, document=a.id).created == 1
    assert engine.compile_document(ctx, document=b.id).created == 1


def test_rule_tally_is_reported(engine, ctx):
    doc = _doc(engine, ctx)
    result = engine.compile_document(ctx, document=doc.id)
    assert result.by_rule
    assert sum(result.by_rule.values()) == result.created
    assert list(result.by_rule) == sorted(result.by_rule)


def test_compiling_requires_the_ingest_capability(engine, ctx):
    from epistemos.errors import AuthorizationError
    from epistemos.identity import Principal

    doc = _doc(engine, ctx)
    reader = Principal(tenant=ctx.tenant, agent=ctx.agent, namespace=ctx.namespace,
                       capabilities=frozenset({"read"}))
    with pytest.raises(AuthorizationError):
        engine.compile_document(reader, document=doc.id)


def test_compiling_a_non_document_is_refused(engine, ctx):
    src = engine.add_source(ctx, uri="mem://x", trust=0.5)
    with pytest.raises(ValidationError):
        engine.compile_document(ctx, document=src.id)


def test_compiling_an_unknown_document_is_refused(engine, ctx):
    with pytest.raises(NotFoundError):
        engine.compile_document(ctx, document="doc_does_not_exist")


def test_the_core_needs_no_model_to_compile(engine, ctx):
    """NullModelProvider refuses every enrichment; compilation must not depend on any of it."""
    from epistemos.providers import NullModelProvider

    provider = NullModelProvider()
    assert provider.available() is False
    doc = _doc(engine, ctx)
    assert engine.compile_document(ctx, document=doc.id).created > 0


def test_custom_rules_reach_the_engine(engine, ctx):
    rule = PatternRule(
        name="ticket",
        pattern=re.compile(r"\b(?P<subject>[A-Z]+-\d+)\s+is\s+(?P<object>open|closed)\b"),
        predicate="ticket_state",
    )
    doc = _doc(engine, ctx, text="PAY-42 is open", title="tickets")
    result = engine.compile_document(ctx, document=doc.id, rules=[rule])
    assert [(c.subject, c.predicate, c.object) for c in result.claims] == [
        ("PAY-42", "ticket_state", "open")
    ]


def test_extraction_sort_key_is_total():
    a = Extraction("s", "p", "o", "rule_a", Span(0, 5))
    b = Extraction("s", "p", "o", "rule_b", Span(0, 5))
    assert a.sort_key() < b.sort_key()
