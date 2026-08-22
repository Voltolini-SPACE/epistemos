"""EPISTEMOS quickstart — runnable: `python examples/quickstart.py`.

Demonstrates the sovereign core end to end with no model and no network: a bitemporal
employment history with retroactive correction, provenance, a low-trust contradiction,
a decision, explainable search, integrity verification, and export.
"""

from __future__ import annotations

from epistemos import Engine, Principal


def main() -> None:
    eng = Engine.open(":memory:")  # or Engine.open("knowledge.epistemos") for a local file
    ctx = Principal(tenant="acme", agent="claude", namespace="hr")

    hr = eng.add_source(ctx, uri="mem://hr-system", source_kind="api", trust=0.9)

    # Alice at Alpha (Jan), then Beta (Feb) — modelled with valid time
    f1 = eng.assert_fact(ctx, subject="Alice", predicate="works_at", object="Alpha",
                         valid_from="2026-01-01", source=hr.id)
    eng.end_fact(ctx, f1.id, valid_to="2026-02-01", reason="left Alpha")
    eng.assert_fact(ctx, subject="Alice", predicate="works_at", object="Beta",
                    valid_from="2026-02-01", source=hr.id)

    print("current employer:", eng.current(ctx, subject="Alice", predicate="works_at"))       # Beta
    print("as of 2026-01-15:",  # Alpha
          eng.as_of(ctx, "2026-01-15", subject="Alice", predicate="works_at"))

    # A low-trust rumor contradicts the record but does NOT become current
    rumor = eng.add_source(ctx, uri="mem://watercooler", trust=0.05)
    fr = eng.assert_fact(ctx, subject="Alice", predicate="works_at", object="Gamma",
                         source=rumor.id)
    beta = eng.facts_for(ctx, subject="Alice", object="Beta")[0]
    eng.contradict(ctx, fr.id, by=beta.id, note="rumor vs HR")
    print("still current (authority wins):",
          eng.current(ctx, subject="Alice", predicate="works_at"))

    # A decision with evidence, and its lineage
    dec = eng.record_decision(ctx, statement="Assign Alice to Beta account",
                              evidence=[beta.id], outcome="assigned")
    print("decision evidence:", [e["id"] for e in eng.explain(ctx, dec.id)["evidence"]])

    # Explainable retrieval + integrity + export
    top = eng.search(ctx, text="Alice works", limit=1)[0]
    print("top result why:", top["why_returned"])
    print("integrity: verified", eng.verify_integrity(), "events")
    print("export event_count:", eng.export()["event_count"])


if __name__ == "__main__":
    main()
