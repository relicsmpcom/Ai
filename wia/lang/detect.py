"""Dutch / English language identification.

Two independent votes are combined:

1. *token evidence* — share of tokens that are language-exclusive markers;
2. *orthographic evidence* — character n-grams (``ij``, ``sch`` vs ``th``,
   ``tion``), which keep working on 5-word inputs where token overlap is
   ambiguous ("in de" vs "in the").

Anything that convinces neither vote comes back as ``UNKNOWN`` with a low
confidence rather than being forced into one of the two supported languages.
"""

from __future__ import annotations

from dataclasses import dataclass

from wia.lang import resources as R
from wia.text.tokens import words
from wia.types import Language


@dataclass(frozen=True)
class LanguageGuess:
    language: Language
    confidence: float
    nl_score: float
    en_score: float

    def to_dict(self) -> dict:
        return {
            "language": self.language.value,
            "confidence": round(self.confidence, 4),
            "nl_score": round(self.nl_score, 4),
            "en_score": round(self.en_score, 4),
        }


def _ngram_score(lowered: str, ngrams) -> float:
    if not lowered:
        return 0.0
    hits = sum(lowered.count(g) for g in ngrams)
    return hits / max(1, len(lowered) / 10)


def detect_language(text: str) -> LanguageGuess:
    toks = words(text)
    if not toks:
        return LanguageGuess(Language.UNKNOWN, 0.0, 0.0, 0.0)

    n = len(toks)
    nl_hits = sum(1 for t in toks if t in R._NL_MARKERS)
    en_hits = sum(
        1
        for t in toks
        if t in R._EN_MARKERS
        or t.split("'")[0] in R._EN_CONTRACTION_STEMS
        or "'" in t
    )
    nl_tok, en_tok = nl_hits / n, en_hits / n

    lowered = " " + text.lower() + " "
    nl_ng = _ngram_score(lowered, R._NL_NGRAMS)
    en_ng = _ngram_score(lowered, R._EN_NGRAMS)
    ng_total = nl_ng + en_ng or 1.0

    # Token evidence dominates once there is enough of it; n-grams carry short
    # inputs.  The crossover sits around 25 tokens.
    token_weight = min(1.0, n / 25.0) * 0.75 + 0.25
    nl = token_weight * nl_tok + (1 - token_weight) * (nl_ng / ng_total)
    en = token_weight * en_tok + (1 - token_weight) * (en_ng / ng_total)

    total = nl + en
    if total <= 1e-9:
        return LanguageGuess(Language.UNKNOWN, 0.0, nl, en)

    lang = Language.NL if nl >= en else Language.EN

    # Confidence blends separation with sample size.
    separation = abs(nl - en) / total
    size = min(1.0, n / 40.0)
    confidence = max(0.0, min(1.0, 0.25 + 0.55 * separation + 0.20 * size))
    if separation < 0.10 and n < 12:
        return LanguageGuess(Language.UNKNOWN, confidence * 0.5, nl, en)
    return LanguageGuess(lang, confidence, nl, en)
