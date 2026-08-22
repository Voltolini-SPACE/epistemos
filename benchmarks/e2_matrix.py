"""E-2 matrix — vary the tokenizer, hold the scorer, measure everything.

The engine's scorer is *not* touched. Each variant is a real `Engine` fed the same 520-document
corpus with a different tokenizer, queried with the same 170 queries against the same independent
ground truth. Any delta is therefore attributable to lexical representation alone (mission §3, §5).

The regression matrix is separate from the global average on purpose (mission §6): a variant that
lifts morphology while dropping `exact` from 1.000 has not improved retrieval, it has moved the
damage somewhere less visible.

Run: `python benchmarks/e2_matrix.py`
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from e1_corpus import CONCEPTS, build_corpus, corpus_digest  # noqa: E402
from e1_retrieval import CATS, evaluate  # noqa: E402
from e2_tokenizers import (  # noqa: E402
    AccentFolding,
    AliasExpanding,
    CharNgram,
    Composed,
    E1Baseline,
    HyphenSplitting,
    PluralNormalising,
    PossessiveStripping,
    build_alias_table,
)

from epistemos import Engine, Principal  # noqa: E402

TENANT = "acme"
CTX = Principal(tenant=TENANT, agent="bench", namespace="kb")

#: Categories the E-1 report established as solved. A drop here is a critical regression and
#: disqualifies a variant no matter what it gains elsewhere.
CRITICAL = ("exact", "temporal", "conflict", "crossref")
#: How much a critical category may move before it counts as a regression. Not zero: floating
#: point and tie-breaks can wobble a category by a hair without anything meaningful changing.
CRITICAL_TOLERANCE = 0.01


def measure(tokenizer, docs, queries):
    """Ingest under one tokenizer, run every query, return metrics plus cost."""
    eng = Engine.open(None, tokenizer=tokenizer)
    t0 = time.perf_counter()
    ids = {}
    for d in docs:
        o = eng.ingest_document(CTX, title=d.title, text=d.text)
        ids[o.id] = d.doc_id
    ingest_ms = (time.perf_counter() - t0) * 1000

    per_cat: dict[str, list[dict[str, float]]] = {}
    lat: list[float] = []
    for q in queries:
        t = time.perf_counter()
        res = eng.search(CTX, text=q.query, limit=25)
        lat.append((time.perf_counter() - t) * 1000)
        seen, order = set(), []
        for r in res:
            n = ids.get(r["id"])
            if n and n not in seen:
                seen.add(n)
                order.append(n)
        per_cat.setdefault(q.category, []).append(evaluate(order, set(q.expected_documents)))

    # Index cost, measured the honest way: how many terms the tokenizer actually emits.
    term_count = sum(len(tokenizer.tokens(d.text)) for d in docs)
    eng.close()

    allm = [m for v in per_cat.values() for m in v]
    agg = {k: statistics.mean(m[k] for m in allm) for k in allm[0]}
    lat.sort()
    agg["_p50"] = statistics.median(lat)
    agg["_p95"] = lat[int(0.95 * len(lat))]
    agg["_ingest_ms"] = ingest_ms
    agg["_terms"] = float(term_count)
    return agg, per_cat


def cat_mean(per_cat, category, metric="nDCG@10"):
    vals = per_cat.get(category)
    return statistics.mean(m[metric] for m in vals) if vals else float("nan")


def main() -> int:
    docs, queries = build_corpus()
    docs_t = [d for d in docs if d.tenant == TENANT]
    qs = [q for q in queries if q.tenant == TENANT]
    aliases = build_alias_table(CONCEPTS)
    aliases_no_para = build_alias_table(CONCEPTS, include_paraphrase=False)

    print(f"corpus {len(docs)} docs ({len(docs_t)} in {TENANT}), {len(qs)} queries")
    print(f"digest {corpus_digest(docs, queries)}")
    print(f"alias table: {len(aliases)} entries (with paraphrase cues), "
          f"{len(aliases_no_para)} without\n")

    variants = [
        ("A  baseline (E-1, shipped)",     E1Baseline()),
        # -- B: isolated normalisations ------------------------------------
        ("B1 + accent folding",            AccentFolding()),
        ("B2 + plural normalisation",      PluralNormalising()),
        ("B3 + possessive stripping",      PossessiveStripping()),
        ("B4 + hyphen compounds",          HyphenSplitting()),
        # -- C: aliases, split by mechanism --------------------------------
        ("C1 + aliases (explicit only)",   AliasExpanding(aliases_no_para, version="explicit")),
        ("C2 + aliases (+ paraphrase)",    AliasExpanding(aliases, version="para")),
        # -- D: character n-grams ------------------------------------------
        ("D3 + char 3-grams",              CharNgram(3)),
        ("D4 + char 4-grams",              CharNgram(4)),
        ("D5 + char 5-grams",              CharNgram(5)),
    ]

    results = []
    for label, tok in variants:
        agg, per = measure(tok, docs_t, qs)
        results.append((label, tok, agg, per))
        print(f"  measured {label}")

    base_label, _base_tok, base_agg, base_per = results[0]

    # -- E: compose only the transformations that earned it -----------------
    winners = []
    for label, tok, agg, per in results[1:]:
        gain = agg["nDCG@10"] - base_agg["nDCG@10"]
        crit_ok = all(cat_mean(per, c) >= cat_mean(base_per, c) - CRITICAL_TOLERANCE
                      for c in CRITICAL)
        if gain > 0.001 and crit_ok:
            winners.append((label, tok, gain))
    print(f"\n  variants clearing the gate individually: "
          f"{[w[0].split()[0] for w in winners] or 'none'}")

    combos: list[tuple[str, object]] = []
    if winners:
        stages: list[tuple[str, object]] = []
        parts = []
        for label, _tok, _g in sorted(winners, key=lambda w: -w[2]):
            code = label.split()[0]
            if code.startswith("B2"):
                stages.append(("singular", None))
                parts.append("plural")
            elif code.startswith("C1"):
                stages.append(("alias", aliases_no_para))
                parts.append("alias")
            elif code.startswith("C2"):
                stages.append(("alias", aliases))
                parts.append("alias+para")
            elif code.startswith("D"):
                stages.append(("ngram", int(code[1])))
                parts.append(f"ngram{code[1]}")
        if stages:
            combos.append((f"E  compose: {' + '.join(parts)}",
                           Composed(E1Baseline(), stages, name="e2-composed")))
    # A composition worth testing even if its parts did not individually clear the gate: plural
    # normalisation targets morphology and aliases target paraphrase — different categories, so
    # they may add rather than cancel.
    combos.append(("E2 compose: plural + alias(explicit)",
                   Composed(E1Baseline(), [("singular", None), ("alias", aliases_no_para)],
                            name="e2-plural-alias")))
    for label, tok in combos:
        agg, per = measure(tok, docs_t, qs)
        results.append((label, tok, agg, per))
        print(f"  measured {label}")

    # ---------------------------------------------------------------- global
    print("\n" + "=" * 104)
    print(f"{'variant':38s}{'P@1':>8s}{'MRR':>8s}{'nDCG@10':>9s}{'Δ nDCG':>9s}"
          f"{'p50 ms':>9s}{'terms':>11s}")
    print("=" * 104)
    for label, _tok, agg, _per in results:
        d = agg["nDCG@10"] - base_agg["nDCG@10"]
        mark = "" if label == base_label else f"{d:+9.3f}"
        print(f"{label:38s}{agg['P@1']:8.3f}{agg['MRR']:8.3f}{agg['nDCG@10']:9.3f}"
              f"{mark:>9s}{agg['_p50']:9.3f}{agg['_terms']:11,.0f}")

    # ------------------------------------------------------------ by category
    print("\n" + "=" * 118)
    print(f"nDCG@10 by category{'':19s}" + "".join(f"{c[:9]:>10s}" for c in CATS))
    print("=" * 118)
    for label, _tok, _agg, per in results:
        print(f"{label:38s}" + "".join(f"{cat_mean(per, c):10.3f}" for c in CATS))

    # ------------------------------------------------------- regression matrix
    print("\n" + "=" * 104)
    print("REGRESSION MATRIX — critical categories (a drop here disqualifies, whatever the global)")
    print("=" * 104)
    print(f"{'variant':38s}" + "".join(f"{c:>13s}" for c in CRITICAL) + f"{'verdict':>14s}")
    print("-" * 104)
    for label, _tok, agg, per in results:
        cells, worst = "", 0.0
        for c in CRITICAL:
            d = cat_mean(per, c) - cat_mean(base_per, c)
            worst = min(worst, d)
            cells += f"{d:+13.3f}"
        gain = agg["nDCG@10"] - base_agg["nDCG@10"]
        if label == base_label:
            verdict = "baseline"
        elif worst < -CRITICAL_TOLERANCE:
            verdict = "REGRESSION"
        elif gain > 0.001:
            verdict = "eligible"
        else:
            verdict = "no gain"
        print(f"{label:38s}{cells}{verdict:>14s}")

    # ------------------------------------------------------------------ pick
    eligible = [
        (label, agg, per) for label, _t, agg, per in results
        if label != base_label
        and all(cat_mean(per, c) >= cat_mean(base_per, c) - CRITICAL_TOLERANCE for c in CRITICAL)
        and agg["nDCG@10"] > base_agg["nDCG@10"] + 0.001
    ]
    print("\n" + "=" * 104)
    if not eligible:
        print("DECISION = PASS_NO_CHANGE — no variant both gained globally and held every "
              "critical category.")
    else:
        best = max(eligible, key=lambda e: e[1]["nDCG@10"])
        print(f"WINNER = {best[0]}")
        print(f"  nDCG@10 {base_agg['nDCG@10']:.3f} -> {best[1]['nDCG@10']:.3f}  "
              f"({best[1]['nDCG@10'] - base_agg['nDCG@10']:+.3f})")
        print(f"  MRR     {base_agg['MRR']:.3f} -> {best[1]['MRR']:.3f}")
        print(f"  P@1     {base_agg['P@1']:.3f} -> {best[1]['P@1']:.3f}")
        for c in CATS:
            b, a = cat_mean(base_per, c), cat_mean(best[2], c)
            if abs(a - b) > 0.001:
                print(f"    {c:14s} {b:.3f} -> {a:.3f}  {a - b:+.3f}")
        print(f"  latency p50 {base_agg['_p50']:.3f} -> {best[1]['_p50']:.3f} ms")
        print(f"  index terms {base_agg['_terms']:,.0f} -> {best[1]['_terms']:,.0f} "
              f"({best[1]['_terms'] / base_agg['_terms']:.2f}x)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
