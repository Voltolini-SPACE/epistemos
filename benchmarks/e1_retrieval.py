"""E-1 retrieval matrix — measure every candidate scorer on one corpus, one ground truth.

Mission §8 asks for a comparison, not a winner chosen in advance. Each variant below is a scoring
function over the same 520 documents, evaluated against the same independently-generated relevance
labels, with the same metrics. A variant is adopted only if it shows a measured delta (§17).

Nothing here changes the engine. Variants that beat the baseline become a *proposal*; the
implementation happens afterwards, against these numbers.

Run: `python benchmarks/e1_retrieval.py [--quick]`
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from e1_corpus import CONCEPTS, build_corpus, corpus_digest  # noqa: E402

from epistemos import Engine, Principal  # noqa: E402

TENANT = "acme"
CTX = Principal(tenant=TENANT, agent="bench", namespace="kb")

# ---------------------------------------------------------------------------
# metrics


def dcg(gains: list[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg(order: list[str], want: set[str], k: int) -> float:
    gains = [1.0 if d in want else 0.0 for d in order[:k]]
    ideal = [1.0] * min(len(want), k)
    idcg = dcg(ideal)
    return (dcg(gains) / idcg) if idcg else 0.0


def evaluate(order: list[str], want: set[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k in (1, 3, 5):
        top = order[:k]
        out[f"P@{k}"] = (len([d for d in top if d in want]) / len(top)) if top else 0.0
    for k in (5, 10):
        out[f"R@{k}"] = (len(set(order[:k]) & want) / len(want)) if want else 0.0
    rr = 0.0
    for i, d in enumerate(order, 1):
        if d in want:
            rr = 1.0 / i
            break
    out["MRR"] = rr
    out["nDCG@5"] = ndcg(order, want, 5)
    out["nDCG@10"] = ndcg(order, want, 10)
    return out


# ---------------------------------------------------------------------------
# scorers under test

_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)

# Stop words for EN/PT/ES. Deliberately small and explicit: a list a reviewer can read
# beats a lexicon nobody audits.
STOPWORDS = frozenset([
    "a", "an", "the", "of", "to", "in", "on", "at", "for", "from", "by", "with", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "do", "does", "did", "how", "what",
    "when", "where", "who", "whom", "which", "why", "this", "that", "these", "those", "it",
    "its", "as", "we", "our", "you", "your", "they", "their", "there", "here", "long", "about",
    "into", "over", "under", "more", "most", "some", "any", "all", "can", "could", "should",
    "would", "o", "os", "de", "da", "dos", "das", "em", "no", "na", "nos", "nas", "para",
    "por", "com", "e", "ou", "que", "qual", "quais", "um", "uma", "el", "la", "los", "las",
    "del", "al", "en", "y", "cual", "cuales", "un", "una"
])

# Deterministic accent folding: no dependency, no locale, fully reversible to inspect.
_FOLD = str.maketrans(
    "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ",
    "aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN",
)

#: Deterministic, auditable alias table built from the corpus vocabulary. Every entry is a
#: declared editorial decision, not a learned association — that is the point (mission §18).
ALIASES: dict[str, tuple[str, ...]] = {}
for _c in CONCEPTS:
    _en, _pt, _es, _syns, _paras = _c
    canon = tuple(_TOKEN.findall(_en.lower()))
    for variant in (_pt, _es, *_syns):
        for tok in _TOKEN.findall(variant.translate(_FOLD).lower()):
            if tok not in STOPWORDS:
                ALIASES.setdefault(tok, ())
                ALIASES[tok] = tuple(dict.fromkeys(ALIASES[tok] + canon))
    # paraphrase cues map their content words onto the canonical term
    for phrase in _paras:
        for tok in _TOKEN.findall(phrase.lower()):
            if tok not in STOPWORDS and len(tok) > 3:
                ALIASES.setdefault(tok, ())
                ALIASES[tok] = tuple(dict.fromkeys(ALIASES[tok] + canon))


def _stem(w: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ies", "ers", "ed", "es", "er", "ly", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            base = w[: -len(suf)]
            if suf in ("ing", "ed") and len(base) > 2 and base[-1] == base[-2]:
                base = base[:-1]
            return base
    return w


def prep(text: str, *, fold: bool, stop: bool, stem: bool, alias: bool,
         ngram: int = 0) -> list[str]:
    t = text.translate(_FOLD) if fold else text
    toks = _TOKEN.findall(t.lower())
    if stop:
        toks = [x for x in toks if x not in STOPWORDS]
    if alias:
        expanded: list[str] = []
        for x in toks:
            expanded.append(x)
            expanded.extend(ALIASES.get(x, ()))
        toks = expanded
    if stem:
        toks = [_stem(x) for x in toks]
    if ngram:
        grams = []
        for x in toks:
            grams.append(x)
            grams.extend(x[i:i + ngram] for i in range(max(0, len(x) - ngram + 1)))
        toks = grams
    return toks


class Index:
    """One configurable lexical index. Ties break on document id, always, by construction."""

    def __init__(self, docs, *, fold=False, stop=False, stem=False, alias=False,
                 ngram=0, idf=False, bm25=False, k1=1.5, b=0.75):
        self.cfg = dict(fold=fold, stop=stop, stem=stem, alias=alias, ngram=ngram)
        self.idf, self.bm25, self.k1, self.b = idf, bm25, k1, b
        self.tf, self.len = {}, {}
        df: Counter[str] = Counter()
        for d in docs:
            toks = prep(d.text + " " + d.title, **self.cfg)
            self.tf[d.doc_id] = Counter(toks)
            self.len[d.doc_id] = len(toks)
            df.update(set(toks))
        self.df = df
        self.N = len(self.tf)
        self.avg = statistics.mean(self.len.values()) if self.len else 1.0
        # inverted index so a query touches only matching documents
        self.post: dict[str, list[str]] = {}
        for did, c in self.tf.items():
            for term in c:
                self.post.setdefault(term, []).append(did)

    def _idf(self, term: str) -> float:
        if not (self.idf or self.bm25):
            return 1.0
        n = self.df.get(term, 0)
        return math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def search(self, query: str, limit: int = 25) -> list[str]:
        q = prep(query, **self.cfg)
        scores: dict[str, float] = {}
        for term in q:
            idf = self._idf(term)
            for did in self.post.get(term, ()):
                f = self.tf[did][term]
                if self.bm25:
                    dl = self.len[did]
                    s = idf * (f * (self.k1 + 1)) / (
                        f + self.k1 * (1 - self.b + self.b * dl / (self.avg or 1)))
                elif self.idf:
                    s = idf * f
                else:
                    s = float(f)
                scores[did] = scores.get(did, 0.0) + s
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [d for d, _ in ranked[:limit]]


# ---------------------------------------------------------------------------


def run(label, search_fn, queries, limit=25):
    per_cat: dict[str, list[dict[str, float]]] = {}
    lat = []
    for q in queries:
        t0 = time.perf_counter()
        order = search_fn(q.query, limit)
        lat.append((time.perf_counter() - t0) * 1000)
        per_cat.setdefault(q.category, []).append(evaluate(order, set(q.expected_documents)))
    allm = [m for v in per_cat.values() for m in v]
    agg = {k: statistics.mean(m[k] for m in allm) for k in allm[0]}
    agg["_lat_p50"] = statistics.median(lat)
    agg["_lat_p95"] = sorted(lat)[int(0.95 * len(lat))]
    return label, agg, per_cat


CATS = ["exact", "morphology", "synonym", "paraphrase", "crosslingual", "temporal",
        "conflict", "crossref", "adversarial"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip the live-engine baseline")
    args = ap.parse_args()

    docs, queries = build_corpus()
    docs_t = [d for d in docs if d.tenant == TENANT]
    qs = [q for q in queries if q.tenant == TENANT]
    print(f"corpus: {len(docs)} docs ({len(docs_t)} in tenant {TENANT}), {len(qs)} queries")
    print(f"digest: {corpus_digest(docs, queries)}\n")

    variants = []

    if not args.quick:
        eng = Engine.open(None)
        ids = {}
        t0 = time.perf_counter()
        for d in docs_t:
            o = eng.ingest_document(CTX, title=d.title, text=d.text)
            ids[o.id] = d.doc_id
        ingest_ms = (time.perf_counter() - t0) * 1000
        print(f"ingest: {len(docs_t)} docs in {ingest_ms:.0f} ms "
              f"({ingest_ms / len(docs_t):.2f} ms/doc)\n")

        def engine_search(query: str, limit: int) -> list[str]:
            seen, out = set(), []
            for r in eng.search(CTX, text=query, limit=limit):
                o = r.get("object", r)
                meta = o.get("metadata") or {}
                n = (ids.get(o.get("id")) or ids.get(meta.get("compiled_from"))
                     or ids.get(o.get("origin")))
                if n and n not in seen:
                    seen.add(n)
                    out.append(n)
            return out

        variants.append(run("BASELINE engine (FTS5 + scorer)", engine_search, qs))
        eng.close()

    matrix = [
        ("A  raw overlap",            dict()),
        ("A2 + accent folding",       dict(fold=True)),
        ("A3 + folding + stopwords",  dict(fold=True, stop=True)),
        ("B  + IDF",                  dict(fold=True, stop=True, idf=True)),
        ("C  + BM25",                 dict(fold=True, stop=True, bm25=True)),
        ("C2 + BM25 + stemming",      dict(fold=True, stop=True, bm25=True, stem=True)),
        ("D  + BM25 + char 4-grams",  dict(fold=True, stop=True, bm25=True, ngram=4)),
        ("E  + BM25 + stem + ALIASES", dict(fold=True, stop=True, bm25=True, stem=True,
                                            alias=True)),
    ]
    for label, cfg in matrix:
        idx = Index(docs_t, **cfg)
        variants.append(run(label, idx.search, qs))

    cols = ["P@1", "P@3", "P@5", "R@5", "R@10", "MRR", "nDCG@5", "nDCG@10"]
    print("=" * 118)
    print(f"{'variant':32s}" + "".join(f"{c:>9s}" for c in cols) + f"{'p50 ms':>9s}")
    print("=" * 118)
    for label, agg, _ in variants:
        print(f"{label:32s}" + "".join(f"{agg[c]:9.3f}" for c in cols)
              + f"{agg['_lat_p50']:9.3f}")

    print()
    print("=" * 118)
    print(f"nDCG@10 by category{'':13s}" + "".join(f"{c[:9]:>10s}" for c in CATS))
    print("=" * 118)
    for label, _agg, per in variants:
        cells = "".join(
            f"{statistics.mean(m['nDCG@10'] for m in per[c]):10.3f}" if c in per
            else f"{'-':>10s}" for c in CATS)
        print(f"{label:32s}{cells}")

    base = variants[0]
    best = max(variants, key=lambda v: (v[1]["nDCG@10"], v[1]["MRR"]))
    print(f"\nbaseline : {base[0]}  nDCG@10={base[1]['nDCG@10']:.3f} MRR={base[1]['MRR']:.3f}")
    print(f"best     : {best[0]}  nDCG@10={best[1]['nDCG@10']:.3f} MRR={best[1]['MRR']:.3f}")
    d_ndcg = best[1]["nDCG@10"] - base[1]["nDCG@10"]
    print(f"delta    : nDCG@10 {d_ndcg:+.3f}  "
          f"MRR {best[1]['MRR'] - base[1]['MRR']:+.3f}")
    print("\nper-category delta (best - baseline), nDCG@10:")
    for c in CATS:
        if c in base[2] and c in best[2]:
            db = statistics.mean(m["nDCG@10"] for m in base[2][c])
            dv = statistics.mean(m["nDCG@10"] for m in best[2][c])
            flag = "  REGRESSION" if dv < db - 0.01 else ""
            print(f"  {c:14s} {db:6.3f} -> {dv:6.3f}   {dv - db:+.3f}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
