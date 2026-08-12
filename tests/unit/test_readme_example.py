"""EPISTEMOS-03 audit OV-01: the README/quickstart flagship example must actually run.

The v0.2 README modelled "Alice left X" with supersede(object=None), which closes belief
entirely, so its documented `as_of("2026-01-15") -> "X"` returned None. The example now uses
end_fact (ending world-validity while preserving the value), and this test pins its outputs so
the flagship example cannot drift from the code again.
"""

from __future__ import annotations

from epistemos import Engine, Principal


def test_readme_bitemporal_example() -> None:
    eng = Engine.open(":memory:")
    ctx = Principal(tenant="acme", agent="claude", namespace="hr")

    src = eng.add_source(ctx, uri="mem://note-1", source_kind="note", trust=0.6)
    f = eng.assert_fact(ctx, subject="Alice", predicate="works_at", object="X",
                        valid_from="2026-01-01", source=src.id)

    eng.end_fact(ctx, f.id, valid_to="2026-02-01", reason="Alice left X")

    assert eng.current(ctx, subject="Alice", predicate="works_at") is None
    assert eng.as_of(ctx, "2026-01-15", subject="Alice", predicate="works_at") == "X"
    genealogy = eng.explain(ctx, f.id)
    assert genealogy["id"] == f.id and genealogy["kind"] == "fact"
    eng.close()
