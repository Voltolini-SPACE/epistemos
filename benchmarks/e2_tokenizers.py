"""E-2 candidate tokenizers — one transformation at a time.

E-1 concluded that the gain available in retrieval is in *representation*, not in ranking: every
scorer that replaced the lexical term also discarded the temporal/exact/authority components and
regressed the categories the engine gets right. So E-2 varies only the tokenizer and keeps the
engine's scorer untouched, which makes the comparison attributable — a delta here is caused by
tokenization and by nothing else.

Each transformation is a separate class so it can be measured in isolation (mission §7). They are
deliberately *not* stacked by default: `E1Baseline + accents + plurals` is a different hypothesis
from each of its parts, and only the matrix can say which part earned the delta.

Everything is standard library, deterministic and side-effect free. Nothing here is installed into
the core until the numbers justify it (mission §17).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence

from epistemos.index.text import Tokenizer

__all__ = [
    "AccentFolding",
    "AliasExpanding",
    "CharNgram",
    "Composed",
    "E1Baseline",
    "HyphenSplitting",
    "PluralNormalising",
    "PossessiveStripping",
]

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_UNICODE_TOKEN_RE = re.compile(r"[^\W]+", re.UNICODE)


class E1Baseline(Tokenizer):
    """Exactly what the engine ships today: ASCII word characters, lowercased."""

    name = "e1-baseline"
    fts_tokenize = "ascii"

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        return [t.lower() for t in _TOKEN_RE.findall(text)]


class AccentFolding(Tokenizer):
    """NFD-decompose and drop combining marks, so `retenção` and `retencao` collide.

    Unicode-aware tokenisation is required for this to matter at all: the ASCII pattern already
    splits `retenção` into `reten` + `o`, which is worse than not folding.
    """

    name = "e2-accents"
    fts_tokenize = "unicode61 remove_diacritics 2"

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        out = []
        for raw in _UNICODE_TOKEN_RE.findall(text):
            decomposed = unicodedata.normalize("NFD", raw.lower())
            folded = "".join(c for c in decomposed if not unicodedata.combining(c))
            if folded:
                out.append(unicodedata.normalize("NFC", folded))
        return out


#: Conservative English plural rules. Deliberately *not* a stemmer: it only removes a trailing
#: plural marker, so `retentions`→`retention` but `audits`→`audit` and `analysis` is untouched.
#: Anything more aggressive starts changing meaning, and a rule you cannot read is a rule you
#: cannot audit.
_KEEP_S = frozenset({
    "as", "is", "us", "gas", "bus", "analysis", "basis", "status", "access", "process",
    "class", "cross", "less", "loss", "miss", "pass", "press", "always", "https",
})


def _singular(word: str) -> str:
    if len(word) <= 3 or word in _KEEP_S or not word.endswith("s"):
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"          # policies -> policy
    if word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]                # approaches -> approach
    if word.endswith("ss"):
        return word
    return word[:-1]                    # retentions -> retention


class PluralNormalising(Tokenizer):
    """Baseline plus a conservative singulariser. Targets the morphology category directly."""

    name = "e2-plurals"
    fts_tokenize = "ascii"

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        return [_singular(t.lower()) for t in _TOKEN_RE.findall(text)]


class PossessiveStripping(Tokenizer):
    """`owner's` -> `owner`. The ASCII pattern already splits on the apostrophe, leaving a
    stray `s` token; this removes that noise rather than adding recall."""

    name = "e2-possessive"
    fts_tokenize = "ascii"

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        raw = [t.lower() for t in _TOKEN_RE.findall(text)]
        return [t for i, t in enumerate(raw)
                if not (t == "s" and i > 0 and len(raw[i - 1]) > 2)]


class HyphenSplitting(Tokenizer):
    """Index a hyphenated compound as the whole *and* its parts.

    `payments-api` already tokenises to `payments` + `api` under the ASCII pattern, so this adds
    the joined form back — a query for the exact identifier should match the identifier, not just
    two common words.
    """

    name = "e2-hyphen"
    fts_tokenize = "ascii"

    _COMPOUND = re.compile(r"[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)+")

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        out = [t.lower() for t in _TOKEN_RE.findall(text)]
        out.extend(m.group(0).lower().replace("-", "") for m in self._COMPOUND.finditer(text))
        return out


class AliasExpanding(Tokenizer):
    """Expand declared aliases onto their canonical terms.

    The alias table is data, not inference: every entry is an editorial decision that a reviewer
    can read, version and revert. Nothing is learned, nothing is probabilistic, and no model is
    consulted — which is what keeps it inside the doctrine (mission §9).
    """

    name = "e2-aliases"
    fts_tokenize = "ascii"

    def __init__(self, table: dict[str, tuple[str, ...]], *, version: str = "1") -> None:
        self.table = table
        self.version = version
        self.name = f"e2-aliases-v{version}"

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        out: list[str] = []
        for t in (x.lower() for x in _TOKEN_RE.findall(text)):
            out.append(t)
            out.extend(self.table.get(t, ()))
        return out


class CharNgram(Tokenizer):
    """Baseline tokens plus character n-grams of each token.

    Blunt but model-free: it makes near-spellings collide by construction. The cost is index size
    and precision — every token becomes many, so unrelated words that share a substring start to
    match. The matrix is there to say whether that trade pays.
    """

    def __init__(self, n: int, *, min_len: int | None = None) -> None:
        self.n = n
        self.min_len = min_len if min_len is not None else n
        self.name = f"e2-ngram{n}"
        self.fts_tokenize = "ascii"

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        out: list[str] = []
        for t in (x.lower() for x in _TOKEN_RE.findall(text)):
            out.append(t)
            if len(t) >= self.min_len:
                out.extend(t[i:i + self.n] for i in range(len(t) - self.n + 1))
        return out


class Composed(Tokenizer):
    """Apply several token-level transformations in a declared order.

    Composition is itself a hypothesis: two transformations that each help can cancel, and only a
    measurement distinguishes that from the sum of their parts.
    """

    def __init__(self, base: Tokenizer, stages: Sequence[tuple[str, object]],
                 *, name: str) -> None:
        self.base = base
        self.stages = tuple(stages)
        self.name = name
        self.fts_tokenize = base.fts_tokenize

    def tokens(self, text: str | None) -> list[str]:
        if not text:
            return []
        out = self.base.tokens(text)
        for kind, arg in self.stages:
            if kind == "singular":
                out = [_singular(t) for t in out]
            elif kind == "alias":
                table: dict[str, tuple[str, ...]] = arg  # type: ignore[assignment]
                expanded: list[str] = []
                for t in out:
                    expanded.append(t)
                    expanded.extend(table.get(t, ()))
                out = expanded
            elif kind == "ngram":
                n: int = arg  # type: ignore[assignment]
                grams: list[str] = []
                for t in out:
                    grams.append(t)
                    if len(t) >= n:
                        grams.extend(t[i:i + n] for i in range(len(t) - n + 1))
                out = grams
            else:  # pragma: no cover - guards a typo in a variant definition
                raise ValueError(f"unknown stage {kind!r}")
        return out


def build_alias_table(concepts: Iterable[tuple], *, include_paraphrase: bool = True
                      ) -> dict[str, tuple[str, ...]]:
    """Derive a declared alias table from the corpus concept list.

    Only content words map, and only onto the canonical English term. A word that would map onto
    more than one concept is dropped rather than made ambiguous: an alias that pulls in two
    unrelated topics is worse than no alias, because it damages precision everywhere it fires.
    """
    votes: dict[str, set[tuple[str, ...]]] = {}
    for concept in concepts:
        en, pt, es, syns, paras = concept
        canon = tuple(_TOKEN_RE.findall(en.lower()))
        variants = [pt, es, *syns] + (list(paras) if include_paraphrase else [])
        for variant in variants:
            folded = "".join(
                c for c in unicodedata.normalize("NFD", variant.lower())
                if not unicodedata.combining(c)
            )
            for tok in _TOKEN_RE.findall(folded):
                if len(tok) <= 3 or tok in canon:
                    continue
                votes.setdefault(tok, set()).add(canon)
    return {tok: next(iter(targets)) for tok, targets in votes.items() if len(targets) == 1}
