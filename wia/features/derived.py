"""Quantities derived from several features at once.

Kept apart from the feature registry because these are *interpretations* — a
formality level is a judgement built from evidence, not a measurement — and
because both the analyzer and the rewrite critics must read the same one.
"""

from __future__ import annotations

from typing import Dict

FORMALITY_LABELS: Dict[int, str] = {
    1: "very casual", 2: "conversational", 3: "neutral",
    4: "professional", 5: "formal", 6: "academic",
}


def estimate_formality(features: Dict[str, float]) -> int:
    """A 1–6 formality level from the evidence, not from one proxy.

    Word length alone is a poor stand-in: Dutch compounds make ordinary
    writing look formal, and a casual English sentence full of long product
    names looks formal too. Blending long words with contractions, connective
    register, first person and exclamation marks is still rough, but it moves
    for the right reasons.
    """
    score = 3.0
    score += 1.3 * _above(features.get("long_word_ratio", 0.17), 0.17, 0.14)
    score += 0.9 * _above(features.get("formal_connective_rate", 0.0), 0.3, 1.6)
    score -= 1.3 * _above(features.get("contraction_rate", 0.0), 0.15, 1.8)
    score -= 0.8 * _above(features.get("exclamation_rate", 0.0), 0.1, 1.0)
    score -= 0.6 * _above(features.get("first_person_rate", 0.0), 0.8, 3.0)
    score -= 0.5 * _above(features.get("casual_connective_rate", 0.0), 0.5, 2.5)
    score += 0.5 * _above(features.get("mean_sentence_len", 17.0), 18.0, 12.0)
    score += 1.4 * _above(features.get("formal_register_rate", 0.0), 0.2, 1.2)
    score -= 1.1 * _above(features.get("casual_register_rate", 0.0), 0.4, 2.0)
    return int(max(1, min(6, round(score))))


def _above(value: float, floor: float, span: float) -> float:
    """0 at ``floor``, 1 at ``floor + span``, clamped."""
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, (value - floor) / span))


def formality_label(level: int) -> str:
    return FORMALITY_LABELS[max(1, min(6, int(level)))]
