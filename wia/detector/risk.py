"""Hard-negative risk profiles.

Sections 6 and 7 of the roadmap list the writers this kind of system hurts:
non-native speakers, dyslexic writers, people who write in highly formal or
legal registers, people whose text has been through a grammar checker,
translated text.  Their writing legitimately shows several of the same surface
patterns as generated text.

So the detector detects *them* too — not to accuse them, but to say "the
evidence here is unreliable" and damp its own confidence before it speaks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Sequence

from wia.features.doc import Doc
from wia.lang.resources import EN_FUNCTION_WORDS, NL_FUNCTION_WORDS


@dataclass(frozen=True)
class RiskFactor:
    key: str
    message: str
    damping: float  # 0..1 — how far to pull the estimate back toward "unclear"

    def to_dict(self) -> dict:
        return {"key": self.key, "message": self.message, "damping": self.damping}


_LEGAL_TERMS = re.compile(
    r"\b(artikel|lid|overeenkomst|aansprakelijk\w*|voorwaarden|bepalingen|"
    r"hierbij verklaart|onverminderd|krachtens|conform|hereinafter|pursuant|"
    r"thereof|herein|liability|indemnif\w+|clause|whereas|shall be deemed)\b",
    re.IGNORECASE,
)
_LITERAL_TRANSLATION = re.compile(
    r"\b(in order to|it is possible to|there exists|the same is valid|"
    r"met betrekking tot het feit|in het kader van|op basis van het feit|"
    r"how do you call|i am agree|according to me)\b",
    re.IGNORECASE,
)


def assess(doc: Doc, features: Dict[str, float]) -> List[RiskFactor]:
    out: List[RiskFactor] = []
    n = doc.n_words

    if n < 40:
        out.append(RiskFactor(
            "very_short",
            "Under 40 words. That is not enough evidence for an authorship "
            "estimate — treat this as unclassified.",
            0.85,
        ))
    elif n < 120:
        # Length is already handled by shrink_toward_human; damping it a
        # second time here would crush every short text into "unclear".
        out.append(RiskFactor(
            "short_text",
            "Short text. Estimates below ~120 words are noticeably less "
            "reliable and are reported with reduced confidence.",
            0.0,
        ))

    if features.get("long_word_ratio", 0) > 0.24 and features.get("first_person_rate", 0) < 0.4 \
            and features.get("formal_connective_rate", 0) > 0.8:
        out.append(RiskFactor(
            "highly_formal",
            "Highly formal register. Formal human writing (policy, government, "
            "academic) shares surface patterns with generated text.",
            0.30,
        ))

    if _LEGAL_TERMS.search(doc.text):
        out.append(RiskFactor(
            "legal_or_boilerplate",
            "Legal or contractual language. This genre is formulaic by "
            "design and is a known false-positive source.",
            0.40,
        ))

    if features.get("mean_sentence_len", 0) < 11 and features.get("mattr", 1) < 0.66 and n >= 60:
        out.append(RiskFactor(
            "simplified_language",
            "Short sentences and a small vocabulary. This is the profile of "
            "plain-language writing, language learners and some dyslexic "
            "writers as much as of generated text.",
            0.40,
        ))

    if _LITERAL_TRANSLATION.search(doc.text):
        out.append(RiskFactor(
            "translation_pattern",
            "Phrasing typical of translated text. Translation flattens style "
            "in ways that resemble generation.",
            0.4,
        ))

    # Code-switching: strong evidence of both languages at once.
    lw = set(doc.words)
    nl_hits = len(lw & NL_FUNCTION_WORDS)
    en_hits = len(lw & EN_FUNCTION_WORDS)
    if nl_hits >= 4 and en_hits >= 4 and min(nl_hits, en_hits) / max(nl_hits, en_hits) > 0.45:
        out.append(RiskFactor(
            "code_switching",
            "The text mixes Dutch and English. Per-language models are less "
            "reliable on mixed-language input.",
            0.3,
        ))

    if features.get("list_marker_ratio", 0) > 0.45:
        out.append(RiskFactor(
            "list_heavy",
            "Mostly bullets or numbered items. Lists have little of the "
            "sentence rhythm this analysis depends on.",
            0.45,
        ))

    if features.get("informality_noise", 0) < 0.05 and features.get("contraction_rate", 0) < 0.2 \
            and features.get("hedge_rate", 0) > 0.5:
        out.append(RiskFactor(
            "possibly_edited",
            "Clean surface with human hedging underneath — consistent with "
            "human writing that has been through a grammar or spelling "
            "checker. Correction tools are not authorship.",
            0.35,
        ))

    return out


def dampen(probs: Sequence[float], factors: Sequence[RiskFactor]) -> List[float]:
    """Blend the estimate toward "not enough evidence" for risky inputs."""
    if not factors:
        return list(probs)
    # Damping does not add up linearly; take the strongest and give the rest a
    # diminishing say.
    ordered = sorted((f.damping for f in factors), reverse=True)
    if not ordered or ordered[0] <= 0.0:
        return list(probs)
    lam = ordered[0]
    for extra in ordered[1:]:
        lam = lam + (1 - lam) * extra * 0.4
    lam = min(0.9, lam)
    neutral = [0.55, 0.28, 0.17]
    return [(1 - lam) * p + lam * q for p, q in zip(probs, neutral)]
