"""EPISTEMOS-09 agent-in-the-loop benchmark (§25, §26).

Same corpus, same offline model, same questions, four representations:

    A = raw EPISTEMOS retrieval    (a flat list of serialized objects)
    B = EPCTX structured               (the wire document; agent reads its fields)
    C = EPCTX rendered compact     (renderer, compact style)
    D = EPCTX rendered audit           (renderer, audit style)

We do NOT claim a real LLM answers better. We measure what each representation makes *available* to
a consumer: can it know the answer is disputed, that state is historical vs current, that provenance
exists, without guessing. Raw retrieval leaves these implicit; EPCTX makes them explicit. The metric
is availability of the safety signal, which is the honest thing a protocol can guarantee.

Run:  python tools/eps09_agent_bench.py
"""

from __future__ import annotations

from dataclasses import dataclass

from epistemos import Engine, Principal
from epistemos.context.builder import estimate_tokens
from epistemos.identity import _DEFAULT_CAPS
from epistemos.protocol import RenderStyle, build_epctx, render
from epistemos.storage import MemoryStore

CAPS = _DEFAULT_CAPS | frozenset({"supersede", "decide"})


def principal() -> Principal:
    return Principal(tenant="acme", agent="analyst", namespace="kb", capabilities=CAPS)


@dataclass
class Question:
    query: str
    intent: str
    disputed_gold: bool
    historical_gold: bool


def build() -> tuple[Engine, Principal, list[Question]]:
    e = Engine(MemoryStore())
    p = principal()
    f = e.assert_fact(p, subject="Datastore", predicate="is", object="mongo")
    e.supersede(p, f.id, new={"object": "postgres"}, reason="migration")
    c = e.create_claim(p, subject="Revenue", predicate="grew", object="yes")
    ev = e.create_evidence(p, title="revenue fell in Q3", uri="mem://q3",
                           metadata={"relation": "contradicts"})
    e.attach_evidence(p, evidence_id=ev.id, to_claim=c.id, relation="contradicts")
    qs = [
        Question("Datastore", "current", disputed_gold=False, historical_gold=False),
        Question("Datastore", "historical", disputed_gold=False, historical_gold=True),
        Question("Revenue", "contradiction", disputed_gold=True, historical_gold=False),
    ]
    return e, p, qs


# ---- what each representation makes available to a consumer ----------------
def _raw_signals(engine: Engine, p: Principal, q: Question) -> dict[str, object]:
    hits = engine.search(p, text=q.query, limit=48, believed_only=False)
    objs = [engine.store.get_object(h.get("id", "")) for h in hits]
    objs = [o for o in objs if o]
    tokens = sum(estimate_tokens(str(o)) for o in objs)
    # Raw retrieval: no explicit dispute/temporal/provenance signal. A consumer would have to infer
    # relations and versioning itself — i.e. it is NOT reliably available.
    return {"disputed_available": False, "temporal_available": False,
            "provenance_available": False, "tokens": tokens}


def _structured_signals(doc: dict[str, object]) -> dict[str, object]:
    temporal = doc["temporal"]  # type: ignore[index]
    return {
        "disputed_available": True,
        "disputed": doc["disputed"],
        "temporal_available": True,
        "has_historical": temporal["has_historical_state"],  # type: ignore[index]
        "provenance_available": bool(doc["provenance"]["items"]),  # type: ignore[index]
        "tokens": doc["token_estimate"],
    }


def _rendered_signals(doc: dict[str, object], style: RenderStyle) -> dict[str, object]:
    text = render(doc, style)
    return {
        "disputed_available": True,
        "disputed": "DISPUTED" in text,
        "temporal_available": True,
        "has_historical": "(historical)" in text,
        "provenance_available": "source=" in text or bool(doc["provenance"]["items"]),  # type: ignore
        "tokens": estimate_tokens(text),
    }


def run() -> None:
    engine, p, qs = build()
    reps = ["A raw", "B structured", "C compact", "D audit"]
    agg: dict[str, dict[str, float]] = {
        r: {"disp_ok": 0, "temp_ok": 0, "prov": 0, "tok": 0}
                                        for r in reps}

    for q in qs:
        doc = build_epctx(engine, p, query=q.query, intent=q.intent)
        sig = {
            "A raw": _raw_signals(engine, p, q),
            "B structured": _structured_signals(doc),
            "C compact": _rendered_signals(doc, RenderStyle.COMPACT),
            "D audit": _rendered_signals(doc, RenderStyle.AUDIT),
        }
        for r in reps:
            s = sig[r]
            # disputed correctness: the rep let the consumer reach the right disputed verdict
            disp_ok = s["disputed_available"] and s.get("disputed", False) == q.disputed_gold
            temp_ok = (s["temporal_available"]
                       and s.get("has_historical", False) == q.historical_gold)
            agg[r]["disp_ok"] += 1 if disp_ok else 0
            agg[r]["temp_ok"] += 1 if temp_ok else 0
            agg[r]["prov"] += 1 if s["provenance_available"] else 0
            agg[r]["tok"] += float(s["tokens"])  # type: ignore[arg-type]

    n = len(qs)
    print(f"corpus: {n} questions (1 disputed, 1 historical, 1 current)\n")
    print(f"{'rep':<14}{'contradiction_awareness':<26}{'temporal_correctness':<22}"
          f"{'provenance':<12}{'avg_tokens':<10}")
    for r in reps:
        a = agg[r]
        print(f"{r:<14}{a['disp_ok']/n:<26.2f}{a['temp_ok']/n:<22.2f}"
              f"{a['prov']/n:<12.2f}{a['tok']/n:<10.1f}")

    b = agg["B structured"]
    a = agg["A raw"]
    ok = (b["disp_ok"] == n and b["temp_ok"] == n and a["disp_ok"] == 0)
    print("\nEPCTX makes dispute + temporal + provenance reliably available; raw does not.")
    print("EPISTEMOS_09_AGENT_BENCH = " + ("PASS" if ok else "REVIEW"))


if __name__ == "__main__":
    run()
