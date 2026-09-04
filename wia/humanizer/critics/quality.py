"""The rewrite quality score (roadmap §14).

Nine components, each 0–100, reported separately as well as combined.  The
combined figure is *not* an average: meaning preservation gates everything —
a rewrite that changed a number cannot be a good rewrite no matter how nicely
it reads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from wia.features import Doc, extract
from wia.humanizer.critics.grammar import grammar_delta
from wia.humanizer.critics.naturalness import naturalness
from wia.humanizer.options import HumanizeOptions
from wia.humanizer.style_dna import StyleProfile, style_match
from wia.lexicons import load as load_lexicon
from wia.meaning.guard import MeaningReport, check as meaning_check

#: Weights for the headline number. Meaning is a gate, not a term.
WEIGHTS = {
    "naturalness": 0.28,
    "style_match": 0.14,
    "grammar": 0.16,
    "readability": 0.10,
    "tone_match": 0.12,
    "repetition": 0.08,
    "structural_variety": 0.07,
    "locale_correctness": 0.05,
}

_TONE_TARGETS: Dict[str, Dict[str, tuple]] = {
    # tone: feature -> (low, high) desirable band
    "casual": {"contraction_rate": (0.8, 6.0), "mean_sentence_len": (6, 18)},
    "friendly": {"first_person_rate": (0.8, 6.0), "mean_sentence_len": (8, 20)},
    "professional": {"mean_sentence_len": (12, 24), "exclamation_rate": (0.0, 0.4)},
    "formal": {"contraction_rate": (0.0, 0.4), "mean_sentence_len": (14, 28)},
    "academic": {"long_word_ratio": (0.16, 0.40), "contraction_rate": (0.0, 0.2)},
    "confident": {"hedge_rate": (0.0, 0.6)},
    "warm": {"first_person_rate": (0.8, 6.0), "second_person_rate": (0.6, 6.0)},
    "concise": {"mean_sentence_len": (6, 18)},
    "persuasive": {"second_person_rate": (0.8, 6.0)},
    "neutral": {},
    "enthusiastic": {"exclamation_rate": (0.3, 3.0)},
    "serious": {"exclamation_rate": (0.0, 0.2), "emoji_rate": (0.0, 0.0)},
    "technical": {"digit_rate": (0.5, 8.0)},
    "humorous": {"contraction_rate": (0.6, 6.0)},
    "empathetic": {"second_person_rate": (0.6, 6.0), "hedge_rate": (0.2, 3.0)},
}


@dataclass
class QualityScore:
    meaning_preservation: float = 100.0
    naturalness: float = 0.0
    style_match: float = 0.0
    grammar: float = 0.0
    readability: float = 0.0
    tone_match: float = 0.0
    repetition: float = 0.0
    structural_variety: float = 0.0
    locale_correctness: float = 0.0
    overall: float = 0.0
    accepted: bool = True
    notes: List[str] = field(default_factory=list)
    meaning: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meaning_preservation": round(self.meaning_preservation, 1),
            "naturalness": round(self.naturalness, 1),
            "style_match": round(self.style_match, 1),
            "grammar": round(self.grammar, 1),
            "readability": round(self.readability, 1),
            "tone_match": round(self.tone_match, 1),
            "repetition": round(self.repetition, 1),
            "structural_variety": round(self.structural_variety, 1),
            "locale_correctness": round(self.locale_correctness, 1),
            "overall": round(self.overall, 1),
            "accepted": self.accepted,
            "notes": self.notes,
            "meaning": self.meaning,
        }


def _in_band(value: float, band: tuple) -> float:
    low, high = band
    if low <= value <= high:
        return 1.0
    span = (high - low) or 1.0
    distance = (low - value) if value < low else (value - high)
    return max(0.0, 1.0 - distance / (span * 1.5 + 1e-9))


def _tone_score(features: Dict[str, float], options: HumanizeOptions) -> float:
    targets = _TONE_TARGETS.get(options.tone, {})
    scores = [_in_band(features.get(k, 0.0), band) for k, band in targets.items()]
    # Formality is scored independently of tone.
    formality_band = {
        1: (0.0, 0.14), 2: (0.05, 0.18), 3: (0.10, 0.22),
        4: (0.14, 0.26), 5: (0.18, 0.32), 6: (0.20, 0.40),
    }[options.formality]
    scores.append(_in_band(features.get("long_word_ratio", 0.16), formality_band))
    return 100.0 * (sum(scores) / len(scores) if scores else 1.0)


def _locale_score(text: str, options: HumanizeOptions, language: str) -> float:
    lex = load_lexicon(language)
    table = (lex.get("locale") or {}).get(options.locale or "")
    if not table:
        return 100.0
    wrong = 0
    for source in table:
        if re.search(rf"(?<![\w'’]){re.escape(source)}(?![\w'’])", text, re.IGNORECASE):
            wrong += 1
    return max(0.0, 100.0 - wrong * 12.0)


def score_rewrite(
    original: str,
    rewrite: str,
    options: HumanizeOptions,
    language: str = "en",
    profile: Optional[StyleProfile] = None,
) -> QualityScore:
    q = QualityScore()
    report: MeaningReport = meaning_check(original, rewrite, language)
    q.meaning_preservation = 100.0 * report.score
    q.meaning = report.to_dict()
    q.accepted = report.passed

    nat = naturalness(rewrite, language)
    q.naturalness = nat.score
    q.notes.extend(nat.notes)

    gram = grammar_delta(original, rewrite, language)
    q.grammar = gram.score
    q.notes.extend(gram.issues)

    doc = Doc(rewrite, language)
    f = extract(doc)
    q.readability = 100.0 * f["readability"]
    q.tone_match = _tone_score(f, options)
    q.repetition = 100.0 * max(0.0, 1.0 - (
        f["repeated_bigram_ratio"] * 3.0 + f["adjacent_sentence_overlap"] * 2.0))
    q.structural_variety = 100.0 * min(1.0, (
        0.5 * min(1.0, f["sentence_len_cv"] / 0.6)
        + 0.3 * min(1.0, f["opening_diversity"] / 0.85)
        + 0.2 * min(1.0, f["paragraph_len_cv"] / 0.4)))
    q.locale_correctness = _locale_score(rewrite, options, language)
    q.style_match = style_match(rewrite, profile) if profile else 100.0

    q.overall = sum(getattr(q, name) * weight for name, weight in WEIGHTS.items())
    if not q.accepted:
        q.overall = 0.0
        q.notes.insert(0, report.summary())
    return q
