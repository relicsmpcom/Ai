"""Calibration and the decision policy.

Two separate jobs, deliberately kept apart:

*Calibration* makes the numbers mean what they say — when the model reports
70%, roughly seven in ten such texts should really be of that class.

*The decision policy* turns calibrated numbers into a label.  It is asymmetric
on purpose.  Accusing a person who wrote their own text is the failure mode
that hurts someone, so "Likely AI" needs far more evidence than "Likely
human", and short inputs are not allowed to produce a strong verdict at all.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from wia.detector.model import softmax
from wia.types import AuthorshipClass, Confidence


def fit_temperature(
    logits: Sequence[Sequence[float]],
    labels: Sequence[int],
    lo: float = 0.25,
    hi: float = 8.0,
    steps: int = 160,
) -> float:
    """Grid + golden refinement on negative log-likelihood."""
    if not logits:
        return 1.0

    def nll(t: float) -> float:
        total = 0.0
        for s, y in zip(logits, labels):
            p = softmax([x / t for x in s])
            total -= math.log(max(1e-12, p[y]))
        return total / len(logits)

    best_t, best = 1.0, float("inf")
    for i in range(steps):
        t = lo + (hi - lo) * i / (steps - 1)
        v = nll(t)
        if v < best:
            best, best_t = v, t
    # local refinement
    span = (hi - lo) / steps
    for _ in range(30):
        for t in (best_t - span, best_t + span):
            if t <= 0.05:
                continue
            v = nll(t)
            if v < best:
                best, best_t = v, t
        span /= 1.6
    return best_t


def expected_calibration_error(
    probs: Sequence[float], correct: Sequence[int], bins: int = 10
) -> float:
    """ECE over confidence bins."""
    if not probs:
        return 0.0
    buckets: List[List[Tuple[float, int]]] = [[] for _ in range(bins)]
    for p, c in zip(probs, correct):
        idx = min(bins - 1, max(0, int(p * bins)))
        buckets[idx].append((p, c))
    n = len(probs)
    ece = 0.0
    for b in buckets:
        if not b:
            continue
        conf = sum(p for p, _ in b) / len(b)
        acc = sum(c for _, c in b) / len(b)
        ece += len(b) / n * abs(conf - acc)
    return ece


def reliability_table(
    probs: Sequence[float], correct: Sequence[int], bins: int = 10
) -> List[Dict[str, float]]:
    rows = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        sel = [(p, c) for p, c in zip(probs, correct) if (lo <= p < hi or (i == bins - 1 and p == 1.0))]
        rows.append({
            "bin_low": lo,
            "bin_high": hi,
            "count": len(sel),
            "mean_confidence": sum(p for p, _ in sel) / len(sel) if sel else 0.0,
            "accuracy": sum(c for _, c in sel) / len(sel) if sel else 0.0,
        })
    return rows


@dataclass
class DecisionPolicy:
    """Thresholds that convert calibrated probabilities into a label."""

    likely_ai: float = 0.86
    mostly_ai: float = 0.66
    likely_human: float = 0.72
    mostly_human: float = 0.52
    mixed_floor: float = 0.42
    # Evidence floors. Below these word counts the detector refuses to commit.
    min_words_any_call: int = 40
    min_words_strong_call: int = 120

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "DecisionPolicy":
        known = {k: v for k, v in (d or {}).items() if k in cls().__dict__}
        return cls(**known)

    def decide(
        self, p_human: float, p_mixed: float, p_ai: float, words: int
    ) -> Tuple[AuthorshipClass, Confidence]:
        top = max(p_human, p_mixed, p_ai)
        margin = top - sorted((p_human, p_mixed, p_ai))[-2]

        if words < self.min_words_any_call:
            return AuthorshipClass.UNCERTAIN, Confidence.LOW

        strong_ok = words >= self.min_words_strong_call

        if p_ai >= self.likely_ai and strong_ok:
            label = AuthorshipClass.LIKELY_AI
        elif p_ai >= self.mostly_ai:
            label = AuthorshipClass.MOSTLY_AI
        elif p_human >= self.likely_human and strong_ok:
            label = AuthorshipClass.LIKELY_HUMAN
        elif p_human >= self.mostly_human:
            label = AuthorshipClass.MOSTLY_HUMAN
        elif p_mixed >= self.mixed_floor:
            label = AuthorshipClass.MIXED
        else:
            label = AuthorshipClass.UNCERTAIN

        # Confidence is evidence, not enthusiasm: it needs both a clear winner
        # and enough text for that winner to mean anything.
        size = min(1.0, words / 250.0)
        strength = 0.55 * top + 0.45 * min(1.0, margin * 2.2)
        score = strength * (0.45 + 0.55 * size)
        if label is AuthorshipClass.UNCERTAIN:
            return label, Confidence.LOW
        if score >= 0.68:
            return label, Confidence.HIGH
        if score >= 0.46:
            return label, Confidence.MEDIUM
        return label, Confidence.LOW


def shrink_toward_human(
    probs: Sequence[float], words: int, floor_words: int = 150, strength: float = 0.55
) -> List[float]:
    """Pull short-text predictions toward the human prior.

    Short texts genuinely carry less evidence; without this the model reports
    the same 90% on 30 words as on 900, which is the single fastest way to
    accuse an innocent writer.
    """
    p = list(probs)
    if words >= floor_words:
        return p
    lam = strength * (1.0 - words / floor_words) ** 1.5
    prior = [0.62, 0.26, 0.12]
    return [(1 - lam) * p[i] + lam * prior[i] for i in range(3)]
