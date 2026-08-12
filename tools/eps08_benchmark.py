"""EPISTEMOS-08 LARGE benchmark: reprove the Context Envelope at scale (§17-§29).

The v0.6 promotion gate. A big, redundant corpus — hundreds of entities whose state was superseded
several times (1000+ state changes), plus true duplicates, corroboration from distinct sources,
contradictions, decisions and reviews — over which we compare:

    A = raw retrieval (engine.context(compact=False), history and all)
    E = Context Envelope (engine.context(compact=True))

Primary gates (any failure = do NOT promote, §27):
    CRITICAL_EVIDENCE_LOSS = 0   CONTRADICTION_LOSS = 0   TEMPORAL_REGRESSION = 0
    ANSWER_CORRECTNESS_DELTA >= 0   TOKEN_REDUCTION > 0

Run:  python tools/eps08_benchmark.py [--entities 250] [--versions 4] [--scale]
"""

from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass, field

from epistemos import Engine, Principal
from epistemos.context.builder import _serialize, estimate_tokens
from epistemos.identity import _DEFAULT_CAPS
from epistemos.storage import MemoryStore

TENANT, NS = "acme", "kb"
CAPS = _DEFAULT_CAPS | frozenset({"supersede", "decide"})


def principal(agent: str = "analyst") -> Principal:
    return Principal(tenant=TENANT, agent=agent, namespace=NS, capabilities=CAPS)


@dataclass
class Query:
    text: str
    intent_type: str                       # current | historical | change | contradiction |
    critical: list[list[str]]              # OR-groups that must be DELIVERED inline
    contradiction: list[str] = field(default_factory=list)
    needs_history: bool = False            # a historical/change query — history must stay inline


@dataclass
class Corpus:
    engine: Engine
    principal: Principal
    ids: dict[str, str]
    queries: list[Query]
    n_changes: int


def build(entities: int = 250, versions: int = 4, probes: int = 24) -> Corpus:
    eng = Engine(MemoryStore())
    p = principal()
    ids: dict[str, str] = {}
    changes = 0
    values = ["planning", "building", "staging", "production", "deprecated", "archived"]

    # hundreds of superseded facts (the temporal redundancy) — a handful are named probes.
    for i in range(entities):
        subj = f"Service{i}"
        f = eng.assert_fact(p, subject=subj, predicate="state", object=values[0])
        changes += 1
        chain = [f.id]
        for v in range(1, versions):
            f = eng.supersede(p, f.id, new={"object": values[v % len(values)]}, reason=f"step{v}")
            changes += 1
            chain.append(f.id)
        if i < probes:
            ids[f"probe{i}_current"] = chain[-1]
            ids[f"probe{i}_prev"] = chain[-2]
            ids[f"probe{i}_curval"] = values[(versions - 1) % len(values)]
            ids[f"probe{i}_subj"] = subj

    # true duplicates: IDENTICAL content (same content_hash) → safe to collapse (keep both ids).
    d1 = eng.create_evidence(p, title="SOC2 audit passed", uri="mem://d1",
                             content_hash="soc2", metadata={"relation": "supports"})
    d2 = eng.create_evidence(p, title="SOC2 audit passed", uri="mem://d2",
                             content_hash="soc2", metadata={"relation": "supports"})
    ids["dup1"], ids["dup2"] = d1.id, d2.id
    # corroboration: same finding, DIFFERENT content (distinct wording/hash) → must NOT collapse,
    # so both independent sources survive (corroboration ≠ duplicate, §24).
    corrA = eng.create_evidence(p, title="Revenue grew per firm A", uri="mem://ca",
                                content_hash="revA", metadata={"relation": "supports"})
    corrB = eng.create_evidence(p, title="Revenue grew per firm B", uri="mem://cb",
                                content_hash="revB", metadata={"relation": "supports"})
    ids["corrA"], ids["corrB"] = corrA.id, corrB.id

    # contradiction + decision lineage
    cc = eng.create_claim(p, subject="Cloudcosts", predicate="are", object="controlled")
    ev = eng.create_evidence(p, title="Cloudcosts bill spiked", uri="mem://spike",
                             metadata={"relation": "contradicts"})
    eng.attach_evidence(p, evidence_id=ev.id, to_claim=cc.id, relation="contradicts")
    ids["costs_claim"], ids["costs_contra"] = cc.id, ev.id
    be = eng.create_evidence(p, title="Postgres benchmark strong", uri="mem://bench",
                             metadata={"relation": "supports"})
    dec = eng.record_decision(p, statement="Adopt Postgres datastore", evidence=[be.id])
    ids["dec"], ids["dec_ev"] = dec.id, be.id

    # -- probe queries across the required types (§18) ------------------------
    # Entity-focused retrieval (the realistic pattern for "what is X's state / history"): the query
    # names the entity, so retrieval returns that entity's version history — which is exactly the
    # redundancy the envelope collapses. The caller states intent (current vs historical), as the
    # engine.context API allows and an agent knows.
    q: list[Query] = []
    for i in range(min(probes, 8)):
        q.append(Query(f"Service{i}", "current", [[f"probe{i}_current"]]))
        q.append(Query(f"Service{i}", "historical", [[f"probe{i}_prev"]], needs_history=True))
    q.append(Query("are Cloudcosts controlled or disputed", "contradiction",
                   [["costs_claim"], ["costs_contra"]], contradiction=["costs_contra"]))
    q.append(Query("why did we adopt Postgres datastore", "decision", [["dec"], ["dec_ev"]]))
    q.append(Query("what does the SOC2 audit say", "current", [["dup1", "dup2"]]))
    q.append(Query("which sources support that Revenue grew", "current",
                   [["corrA"], ["corrB"]]))          # corroboration: BOTH sources must survive
    return Corpus(eng, p, ids, q, changes)


# ---- metrics ---------------------------------------------------------------
def _resolve(groups: list[list[str]], ids: dict[str, str]) -> list[set[str]]:
    return [{ids[k] for k in g if k in ids} for g in groups]


_POOL = 48  # the retrieval depth the envelope sees; the raw baseline is measured at the SAME depth
            # so the token delta is purely the envelope's redundancy collapse, not a smaller pool.


def _raw_ids_and_tokens(eng: Engine, p: Principal, query: str) -> tuple[set[str], int]:
    raw = eng.search(p, text=query, limit=_POOL, believed_only=False)
    ids, toks = set(), 0
    for r in raw:
        o = eng.store.get_object(r.get("id", ""))
        if o is None:
            continue
        ids.add(o["id"])
        toks += estimate_tokens(_serialize(o))
    return ids, toks


@dataclass
class Row:
    baseline_tokens: int
    env_tokens: int
    baseline_correct: bool
    env_correct: bool
    critical_loss: bool
    contradiction_loss: bool
    temporal_regression: bool
    latency_ms: float


def run(corpus: Corpus) -> list[Row]:
    eng, p, ids = corpus.engine, corpus.principal, corpus.ids
    rows: list[Row] = []
    for q in corpus.queries:
        groups = _resolve(q.critical, ids)
        contra = {ids[k] for k in q.contradiction if k in ids}
        base_ids, base_tokens = _raw_ids_and_tokens(eng, p, q.text)
        t0 = time.perf_counter()
        env = eng.context(p, q.text, compact=True, intent=q.intent_type)
        dt = (time.perf_counter() - t0) * 1000
        delivered = {i["object"] for i in env["items"]}
        reachable = set(delivered)
        for g in env["collapsed_groups"]:
            reachable.update(g["collapsed"])
            reachable.add(g["current"])
        # correctness: every gold group has a member delivered inline
        base_correct = all(g & base_ids for g in groups)
        env_correct = all(g & delivered for g in groups)
        # critical evidence loss: something the baseline could reach that the envelope cannot
        base_reach = base_ids
        crit_loss = any((g & base_reach) and not (g & reachable) for g in groups)
        contra_loss = bool(contra) and (contra & base_ids) and not (contra & delivered)
        # temporal regression: a history query where baseline delivered the answer but envelope did
        # not (inline) — history must be preserved for these intents
        temporal_reg = q.needs_history and base_correct and not env_correct
        rows.append(Row(base_tokens, env["token_estimate"], base_correct, env_correct,
                        crit_loss, bool(contra_loss), temporal_reg, dt))
    return rows


def report(corpus: Corpus, rows: list[Row]) -> bool:
    n = len(rows)
    bt = statistics.mean(r.baseline_tokens for r in rows)
    et = statistics.mean(r.env_tokens for r in rows)
    reduction = round(100 * (bt - et) / bt, 1) if bt else 0.0
    base_corr = round(100 * sum(r.baseline_correct for r in rows) / n, 1)
    env_corr = round(100 * sum(r.env_correct for r in rows) / n, 1)
    crit_loss = sum(r.critical_loss for r in rows)
    contra_loss = sum(r.contradiction_loss for r in rows)
    temporal_reg = sum(r.temporal_regression for r in rows)
    lat = sorted(r.latency_ms for r in rows)
    print(f"corpus: {corpus.n_changes} state changes, {corpus.engine.store.event_count()} events, "
          f"{n} probe queries")
    print(f"  tokens: baseline {bt:.1f} -> envelope {et:.1f}  (reduction {reduction:+.1f}%)")
    print(f"  answer_correctness: baseline {base_corr}% -> envelope {env_corr}% "
          f"(delta {env_corr - base_corr:+.1f})")
    print(f"  CRITICAL_EVIDENCE_LOSS={crit_loss}  CONTRADICTION_LOSS={contra_loss}  "
          f"TEMPORAL_REGRESSION={temporal_reg}")
    print(f"  latency p50={lat[n // 2]:.2f}ms p95={lat[min(n - 1, int(0.95 * (n - 1)))]:.2f}ms")
    gates = {
        "CRITICAL_EVIDENCE_LOSS=0": crit_loss == 0,
        "CONTRADICTION_LOSS=0": contra_loss == 0,
        "TEMPORAL_REGRESSION=0": temporal_reg == 0,
        "ANSWER_CORRECTNESS_DELTA>=0": env_corr >= base_corr,
        "TOKEN_REDUCTION>0": reduction > 0,
    }
    ok = all(gates.values())
    print("  GATES: " + ("ALL PASS" if ok else "FAIL"))
    for k, v in gates.items():
        if not v:
            print(f"    FAIL {k}")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entities", type=int, default=250)
    ap.add_argument("--versions", type=int, default=4)
    ap.add_argument("--scale", action="store_true", help="latency sweep at growing sizes")
    args = ap.parse_args()
    if args.scale:
        print("=== scale sweep (token reduction + latency) ===")
        for ent in (100, 500, 2000):
            c = build(entities=ent, versions=4)
            rows = run(c)
            bt = statistics.mean(r.baseline_tokens for r in rows)
            et = statistics.mean(r.env_tokens for r in rows)
            lat = statistics.median(r.latency_ms for r in rows)
            print(f"  entities={ent:>5} events={c.engine.store.event_count():>6}  "
                  f"tokens {bt:.0f}->{et:.0f} ({100 * (bt - et) / bt:+.0f}%)  "
                  f"envelope_latency_p50={lat:.1f}ms")
        return
    corpus = build(entities=args.entities, versions=args.versions)
    ok = report(corpus, run(corpus))
    print("\nEPISTEMOS_08_LARGE_BENCH = " + ("PASS" if ok else "BLOCKED"))


if __name__ == "__main__":
    main()
