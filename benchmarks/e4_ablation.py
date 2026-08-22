"""E-4 ablation — how much do cross-lingual and synonym queries gain from semantics?

Four conditions over the E-3 corpus and index, with the lexical path untouched in all of them:

    L0  lexical only (the E-3 state)
    L1  lexical + declared query expansion
    L2  lexical + distributional candidate generation
    L3  both

Cross-lingual and synonym are reported separately (mission §3) because they are different
problems: one is a language barrier, the other is a vocabulary barrier, and a technique can solve
one while doing nothing for the other.

`false_semantic_positive_rate` (mission §10) is reported alongside. A method that starts returning
plausible-but-wrong documents on `exact`, `conflict` or `adversarial` has regressed, however good
its recall looks — semantics that widens the net is only a win if the extra catch is correct.

Run: `python benchmarks/e4_ablation.py`
"""

from __future__ import annotations

import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from e1_corpus import CONCEPTS, build_corpus  # noqa: E402
from e1_retrieval import evaluate  # noqa: E402
from e4_semantic import (  # noqa: E402
    DistributionalIndex,
    Vocabulary,
    expand_query,
    handwritten_ceiling_vocabulary,
    mine_cooccurrence_vocabulary,
)

from epistemos import Engine, Principal  # noqa: E402

TENANT = "acme"
CTX = Principal(tenant=TENANT, agent="bench", namespace="kb")
TOKENIZER = "plural"                       # the E-3 adopted configuration
CATS = ["exact", "morphology", "synonym", "paraphrase", "crosslingual", "temporal",
        "conflict", "crossref", "adversarial"]
CRITICAL = ("exact", "temporal", "conflict", "crossref", "adversarial")
#: Where a widened net is most likely to catch the wrong thing.
FSP_SETS = ("exact", "conflict", "adversarial")


def build_engine(docs, path):
    eng = Engine.open(path, tokenizer=TOKENIZER)
    ids = {}
    for d in docs:
        o = eng.ingest_document(CTX, title=d.title, text=d.text)
        ids[o.id] = d.doc_id
    assert eng.lexical_index is not None, "the measurement must run on the indexed path"
    return eng, ids


def run(eng, ids, queries, rewrite=None):
    """Evaluate one condition. `rewrite` maps a query to (expanded, receipt) or None for L0."""
    per: dict[str, list[dict[str, float]]] = {}
    fsp: dict[str, list[float]] = {}
    lat: list[float] = []
    receipts: list[dict] = []
    for q in queries:
        text = q.query
        if rewrite is not None:
            text, receipt = rewrite(q.query)
            receipts.append(receipt.to_dict())
        t0 = time.perf_counter()
        res = eng.search(CTX, text=text, limit=25)
        lat.append((time.perf_counter() - t0) * 1000)
        seen, order = set(), []
        for r in res:
            n = ids.get(r["id"])
            if n and n not in seen:
                seen.add(n)
                order.append(n)
        want = set(q.expected_documents)
        per.setdefault(q.category, []).append(evaluate(order, want))
        if q.category in FSP_SETS:
            top = order[:10]
            fsp.setdefault(q.category, []).append(
                (len([d for d in top if d not in want]) / len(top)) if top else 0.0)
    allm = [m for v in per.values() for m in v]
    agg = {k: statistics.mean(m[k] for m in allm) for k in allm[0]}
    lat.sort()
    agg["_p50"] = statistics.median(lat)
    agg["_p95"] = lat[int(0.95 * len(lat))]
    fsp_all = [x for v in fsp.values() for x in v]
    agg["_fsp"] = statistics.mean(fsp_all) if fsp_all else 0.0
    return agg, per, fsp, receipts


def cm(per, c, metric="nDCG@10"):
    return statistics.mean(m[metric] for m in per[c]) if c in per else float("nan")


def subset(per, c):
    """The four metrics the mission asks for, for one evaluation set (§3)."""
    if c not in per:
        return {}
    return {k: statistics.mean(m[k] for m in per[c])
            for k in ("nDCG@10", "MRR", "P@1", "R@10")}


def main() -> int:
    docs, queries = build_corpus()
    dt = [d for d in docs if d.tenant == TENANT]
    qs = [q for q in queries if q.tenant == TENANT]

    mined = mine_cooccurrence_vocabulary(dt)
    ceiling = handwritten_ceiling_vocabulary(CONCEPTS)
    dist = DistributionalIndex(dt)

    print(f"corpus {len(dt)} docs / {len(qs)} queries · tokenizer={TOKENIZER}")
    print(f"vocabularies:\n  {mined.describe()}\n  {ceiling.describe()}")
    print(f"  distributional index: {len(dist.vectors)} term vectors\n")

    # A real temporary directory rather than a predicted name: mktemp leaves a window in which
    # another process can claim the path.
    workdir = tempfile.TemporaryDirectory(prefix="e4-ablation-")
    path = str(Path(workdir.name) / "kb.epistemos")
    eng, ids = build_engine(dt, path)

    conditions = [
        ("L0  lexical only", None),
        ("L1  + expansion (mined)", lambda q: expand_query(q, mined)),
        ("L2  + distributional", dist.expand),
        ("L3  + both (mined)", lambda q: _chain(q, mined, dist)),
        ("XC  + expansion (CEILING, experimental)", lambda q: expand_query(q, ceiling)),
    ]

    results = []
    for label, rewrite in conditions:
        results.append((label, *run(eng, ids, qs, rewrite)))
        print(f"  measured {label}")

    base_label, base_agg, base_per, _bfsp, _br = results[0]

    print("\n" + "=" * 112)
    print(f"{'condition':42s}{'nDCG@10':>9s}{'Δ':>8s}{'MRR':>8s}{'P@1':>8s}"
          f"{'FSP':>8s}{'p50 ms':>9s}")
    print("=" * 112)
    for label, agg, _per, _fsp, _r in results:
        d = agg["nDCG@10"] - base_agg["nDCG@10"]
        mark = "" if label == base_label else f"{d:+8.3f}"
        print(f"{label:42s}{agg['nDCG@10']:9.3f}{mark:>8s}{agg['MRR']:8.3f}"
              f"{agg['P@1']:8.3f}{agg['_fsp']:8.3f}{agg['_p50']:9.3f}")

    # -- the two problems, separately (§3) ---------------------------------
    for target in ("crosslingual", "synonym"):
        print("\n" + "=" * 112)
        print(f"{target.upper()} — {len(base_per.get(target, []))} queries")
        print(f"{'condition':42s}{'nDCG@10':>10s}{'MRR':>9s}{'P@1':>9s}{'R@10':>9s}{'Δ nDCG':>9s}")
        print("-" * 112)
        b = subset(base_per, target)
        for label, _agg, per, _fsp, _r in results:
            s = subset(per, target)
            if not s:
                continue
            d = s["nDCG@10"] - b["nDCG@10"]
            mark = "" if label == base_label else f"{d:+9.3f}"
            print(f"{label:42s}{s['nDCG@10']:10.3f}{s['MRR']:9.3f}{s['P@1']:9.3f}"
                  f"{s['R@10']:9.3f}{mark:>9s}")

    # -- full ablation by category ------------------------------------------
    print("\n" + "=" * 122)
    print(f"nDCG@10 by category{'':23s}" + "".join(f"{c[:9]:>10s}" for c in CATS))
    print("=" * 122)
    for label, _agg, per, _fsp, _r in results:
        print(f"{label:42s}" + "".join(f"{cm(per, c):10.3f}" for c in CATS))

    # -- regression gate (§9) + false semantic positives (§10) --------------
    print("\n" + "=" * 112)
    print("ADOPTION GATE — every critical category must not worsen, and both targets must improve")
    print("=" * 112)
    for label, agg, per, fsp, _r in results[1:]:
        worsened = [c for c in CRITICAL if cm(per, c) < cm(base_per, c) - 0.005]
        cl = cm(per, "crosslingual") - cm(base_per, "crosslingual")
        sy = cm(per, "synonym") - cm(base_per, "synonym")
        gl = agg["nDCG@10"] - base_agg["nDCG@10"]
        d_fsp = agg["_fsp"] - base_agg["_fsp"]
        eligible = (not worsened) and cl > 0.001 and sy > 0.001 and gl > 0.001
        print(f"\n  {label}")
        print(f"    cross-lingual {cl:+.3f} · synonym {sy:+.3f} · global {gl:+.3f} · "
              f"false-positive {d_fsp:+.3f}")
        print(f"    critical worsened: {worsened or 'none'}")
        for c in FSP_SETS:
            if c in fsp:
                print(f"      FSP {c:12s} {statistics.mean(_bfsp[c]):.3f} -> "
                      f"{statistics.mean(fsp[c]):.3f}")
        print(f"    => {'ELIGIBLE' if eligible else 'NOT ELIGIBLE'}")

    # -- determinism (§11) --------------------------------------------------
    print("\n" + "=" * 112)
    print("DETERMINISM — 3 runs per condition, ranking + metrics + receipts")
    print("=" * 112)
    for label, rewrite in conditions:
        sigs = set()
        for _ in range(3):
            agg, per, _f, rec = run(eng, ids, qs, rewrite)
            sigs.add((round(agg["nDCG@10"], 12), round(agg["MRR"], 12),
                      tuple(sorted(str(r) for r in rec))))
        print(f"  {label:42s} {'DETERMINISTIC' if len(sigs) == 1 else 'NON_DETERMINISTIC'}")

    # -- a receipt, shown (§5) ---------------------------------------------
    print("\n" + "=" * 112)
    print("EXPANSION RECEIPTS — sample")
    print("=" * 112)
    for label, vocab_or_idx in (("L1 mined", mined), ("XC ceiling", ceiling)):
        for q in qs:
            if q.category in ("crosslingual", "synonym"):
                _e, r = expand_query(q.query, vocab_or_idx)  # type: ignore[arg-type]
                if r.terms_added:
                    print(f"  {label}: {r.to_dict()}")
                    break
    for q in qs:
        if q.category == "crosslingual":
            _e, r = dist.expand(q.query)
            if r.terms_added:
                print(f"  L2 distributional: {r.to_dict()}")
                break

    eng.close()
    workdir.cleanup()
    return 0


def _chain(query: str, vocab: Vocabulary, dist: DistributionalIndex):
    first, r1 = expand_query(query, vocab, max_added=4)
    second, r2 = dist.expand(first, max_added=4)
    from e4_semantic import ExpansionReceipt

    return second, ExpansionReceipt(
        original_query=query, expanded_query=second,
        rule_id=f"{r1.rule_id}+{r2.rule_id}",
        terms_added=tuple(dict.fromkeys(r1.terms_added + r2.terms_added)),
    )


if __name__ == "__main__":
    sys.exit(main())
