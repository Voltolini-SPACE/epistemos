"""E-4 — semantic candidates for cross-lingual and synonym queries.

E-3 proved the lexical representation and must not be touched (mission §2). Everything here sits
*above* retrieval: it rewrites or augments the **query**, never the persisted index, and it feeds
the existing lexical retriever rather than replacing it.

Two candidate families, deliberately separated so the ablation can attribute any gain:

* **L1 — declared query expansion.** A term maps to other terms through a versioned vocabulary.
  The vocabulary's *origin* is the point (mission §6): one is mined from the corpus by a stated
  algorithm, so it has provenance, coverage and a version; the other is hand-written and is
  therefore labelled experimental and reported separately, never as a production candidate.
* **L2 — distributional candidate generation.** Terms that occur in similar document contexts are
  treated as related. This is a genuine semantic signal computed from the corpus itself: no model,
  no network, no third-party vocabulary, fully deterministic. It is the honest answer to "how much
  can semantics add without a model?"

Nothing here is proposed for the core. E-4 is a measurement.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)

#: Function words carry no topical signal in any of the three corpus languages. Kept small and
#: explicit — a list a reviewer can check beats a lexicon nobody audits.
STOP = frozenset([
    "a", "an", "the", "of", "to", "in", "on", "at", "for", "from", "by", "with", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "do", "does", "did", "how", "what",
    "when", "where", "who", "whom", "which", "why", "this", "that", "these", "those", "it",
    "its", "as", "we", "our", "you", "your", "they", "their", "there", "here", "long",
    "about", "into", "over", "under", "more", "most", "some", "any", "all", "can", "could",
    "should", "would", "not", "o", "os", "de", "da", "dos", "das", "em", "no", "na", "nos",
    "nas", "para", "por", "com", "e", "ou", "que", "qual", "quais", "um", "uma", "seu",
    "sua", "seus", "seja", "ser", "la", "el", "los", "las", "del", "al", "y", "en", "un",
    "una", "es", "son", "su", "sus", "cual", "cuales"
])


def fold(text: str) -> str:
    """NFD-decompose and drop combining marks. Deterministic, locale-free, inspectable."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if not unicodedata.combining(c))


def terms(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(fold(text)) if t not in STOP and len(t) > 2]


# ---------------------------------------------------------------------------
# Expansion receipts (mission §5)


@dataclass(frozen=True, slots=True)
class ExpansionReceipt:
    """What an expansion did, and under which rule — so a wrong result indicts a named rule."""

    original_query: str
    expanded_query: str
    rule_id: str
    terms_added: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "original_query": self.original_query,
            "expanded_query": self.expanded_query,
            "rule_id": self.rule_id,
            "terms_added": list(self.terms_added),
        }


# ---------------------------------------------------------------------------
# Vocabulary provenance (mission §6)


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """A term→terms mapping that knows where it came from.

    A synonym table with no stated origin is unfalsifiable: it cannot be re-derived, its coverage
    cannot be checked, and it can always be quietly widened until the benchmark passes. Recording
    origin, version and coverage is what separates a candidate from a fudge.
    """

    name: str
    version: str
    origin: str
    status: str                       # "derived" | "experimental"
    table: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def coverage(self) -> int:
        return len(self.table)

    def describe(self) -> str:
        return (f"{self.name} v{self.version} [{self.status}] "
                f"{self.coverage} entries — {self.origin}")


def mine_cooccurrence_vocabulary(docs, *, min_df: int = 3, top_k: int = 3,
                                 min_score: float = 0.35, version: str = "1") -> Vocabulary:
    """Derive term associations from the corpus by pointwise-mutual-information-style scoring.

    Origin is the corpus itself: two terms are associated when they co-occur in documents far more
    often than their independent frequencies predict. No external list, no model, no network — and
    re-runnable, so anyone can re-derive the same table from the same corpus.

    This is the *production-shaped* candidate. Its weakness is honest and structural: it can only
    relate terms that already share documents, so it discovers cross-lingual pairs only where the
    two languages happen to describe the same entity.
    """
    doc_terms = [set(terms(d.text)) for d in docs]
    n = len(doc_terms)
    df: Counter[str] = Counter()
    for ts in doc_terms:
        df.update(ts)
    vocab = {t for t, c in df.items() if c >= min_df}

    pair: Counter[tuple[str, str]] = Counter()
    for ts in doc_terms:
        present = sorted(ts & vocab)
        for i, a in enumerate(present):
            for b in present[i + 1:]:
                pair[(a, b)] += 1

    scores: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for (a, b), c in pair.items():
        # Normalised PMI: bounded to [-1, 1], so `min_score` means the same thing at any corpus
        # size. Raw PMI would need a different threshold for every corpus.
        p_ab, p_a, p_b = c / n, df[a] / n, df[b] / n
        if p_ab <= 0:
            continue
        pmi = math.log(p_ab / (p_a * p_b))
        npmi = pmi / -math.log(p_ab)
        if npmi >= min_score:
            scores[a].append((npmi, b))
            scores[b].append((npmi, a))

    table = {}
    for t, cands in scores.items():
        # Sort by score then term so the table is a pure function of the corpus.
        best = [b for _s, b in sorted(cands, key=lambda x: (-x[0], x[1]))[:top_k]]
        if best:
            table[t] = tuple(best)
    return Vocabulary(
        name="corpus-cooccurrence", version=version,
        origin=(f"mined from the benchmark corpus by normalised PMI "
                f"(min_df={min_df}, top_k={top_k}, min_score={min_score})"),
        status="derived", table=table,
    )


def handwritten_ceiling_vocabulary(concepts, *, version: str = "1") -> Vocabulary:
    """A perfect hand-written table, used ONLY to measure the ceiling.

    Mission §6 forbids shipping a list authored to make the benchmark pass. Measuring one is a
    different act: it answers "if the vocabulary were perfect, how much would it buy?" — which is
    exactly what decides whether pursuing a real vocabulary is worth it. Reported as experimental,
    never as a production candidate.
    """
    table: dict[str, set[str]] = defaultdict(set)
    for en, pt, es, syns, paras in concepts:
        canon = tuple(terms(en))
        for variant in (pt, es, *syns, *paras):
            for tok in terms(variant):
                if tok not in canon:
                    table[tok].update(canon)
        for tok in canon:
            for variant in (pt, es):
                table[tok].update(terms(variant))
    return Vocabulary(
        name="handwritten-ceiling", version=version,
        origin="authored from the corpus concept table specifically for this benchmark",
        status="experimental",
        table={k: tuple(sorted(v)) for k, v in table.items() if v},
    )


# ---------------------------------------------------------------------------
# L1 — declared query expansion


def expand_query(query: str, vocab: Vocabulary, *, max_added: int = 8
                 ) -> tuple[str, ExpansionReceipt]:
    """Append vocabulary-declared terms to the query. The original terms are always kept, so an
    expansion can only add recall — it never removes a match the lexical query would have made."""
    original = terms(query)
    added: list[str] = []
    for t in original:
        for extra in vocab.table.get(t, ()):
            if extra not in original and extra not in added:
                added.append(extra)
                if len(added) >= max_added:
                    break
        if len(added) >= max_added:
            break
    expanded = query if not added else query + " " + " ".join(added)
    return expanded, ExpansionReceipt(
        original_query=query, expanded_query=expanded,
        rule_id=f"{vocab.name}@{vocab.version}", terms_added=tuple(added),
    )


# ---------------------------------------------------------------------------
# L2 — distributional candidate generation


class DistributionalIndex:
    """Term vectors over document contexts, with cosine similarity.

    The "semantic representation" of mission §7, built with nothing but the standard library and
    the corpus. A term is represented by the documents it appears in, weighted by inverse document
    frequency; two terms are related when those weighted profiles point the same way.

    It generates *candidate terms*, which then go through the existing lexical retriever. The
    lexical path stays authoritative — semantics only widens what is considered.
    """

    def __init__(self, docs, *, min_df: int = 2, top_k: int = 3, min_sim: float = 0.5) -> None:
        self.top_k, self.min_sim = top_k, min_sim
        doc_terms = [terms(d.text) for d in docs]
        n = len(doc_terms)
        df: Counter[str] = Counter()
        for ts in doc_terms:
            df.update(set(ts))
        self.vocab = sorted(t for t, c in df.items() if c >= min_df)
        idf = {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in self.vocab}

        vectors: dict[str, dict[int, float]] = {t: {} for t in self.vocab}
        for i, ts in enumerate(doc_terms):
            counts = Counter(t for t in ts if t in idf)
            for t, c in counts.items():
                vectors[t][i] = (1.0 + math.log(c)) * idf[t]
        self.vectors = {}
        for t, v in vectors.items():
            norm = math.sqrt(sum(x * x for x in v.values()))
            if norm:
                self.vectors[t] = {k: x / norm for k, x in v.items()}

        self._cache: dict[str, tuple[str, ...]] = {}

    def related(self, term: str) -> tuple[str, ...]:
        if term in self._cache:
            return self._cache[term]
        vec = self.vectors.get(term)
        if not vec:
            self._cache[term] = ()
            return ()
        scored: list[tuple[float, str]] = []
        for other, ovec in self.vectors.items():
            if other == term:
                continue
            small, large = (vec, ovec) if len(vec) < len(ovec) else (ovec, vec)
            sim = sum(x * large.get(k, 0.0) for k, x in small.items())
            if sim >= self.min_sim:
                scored.append((sim, other))
        # score then term: a pure function of the corpus, never of dict iteration order
        out = tuple(t for _s, t in sorted(scored, key=lambda x: (-x[0], x[1]))[:self.top_k])
        self._cache[term] = out
        return out

    def expand(self, query: str, *, max_added: int = 8) -> tuple[str, ExpansionReceipt]:
        original = terms(query)
        added: list[str] = []
        for t in original:
            for extra in self.related(t):
                if extra not in original and extra not in added:
                    added.append(extra)
                    if len(added) >= max_added:
                        break
            if len(added) >= max_added:
                break
        expanded = query if not added else query + " " + " ".join(added)
        return expanded, ExpansionReceipt(
            original_query=query, expanded_query=expanded,
            rule_id=f"distributional@top{self.top_k}/sim{self.min_sim}",
            terms_added=tuple(added),
        )
