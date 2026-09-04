"""The naturalness critic.

**This critic does not consult the detector.** That is a deliberate design
decision, not an oversight. Scoring rewrites by how well they fool the
detector would turn the humanizer into an evasion tool and would corrupt the
detector's own evaluation loop — the two systems would train on each other
until both were measuring nothing.

Instead it measures qualities that make writing good on its own terms:
variation, plainness, flow and moderation. A text that improves on these reads
better to a human. Whether that also changes a detector's opinion is a side
effect nobody here optimises for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from wia.features import Doc, extract


def _band(value: float, low: float, high: float, floor: float = 0.0,
          ceiling: float = 1.0) -> float:
    """1.0 inside [low, high], falling off outside it."""
    if low <= value <= high:
        return 1.0
    span = (high - low) or 1.0
    distance = (low - value) if value < low else (value - high)
    return max(0.0, 1.0 - distance / (span * 1.5))


def _less_is_better(value: float, good: float, bad: float) -> float:
    if value <= good:
        return 1.0
    if value >= bad:
        return 0.0
    return 1.0 - (value - good) / (bad - good)


@dataclass
class NaturalnessReport:
    score: float = 0.0
    parts: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"score": round(self.score, 1),
                "parts": {k: round(v * 100, 1) for k, v in self.parts.items()},
                "notes": self.notes}


WEIGHTS: Tuple[Tuple[str, float], ...] = (
    ("variation", 1.4),
    ("plainness", 1.3),
    ("flow", 1.1),
    ("moderation", 1.0),
    ("shape", 0.8),
)


def naturalness(text: str, language: str = "en") -> NaturalnessReport:
    doc = Doc(text, language)
    f = extract(doc)
    report = NaturalnessReport()

    variation = (
        0.45 * _band(f["sentence_len_cv"], 0.35, 0.85)
        + 0.30 * _band(f["opening_diversity"], 0.70, 1.0)
        + 0.25 * _less_is_better(f["length_step_regularity"], 0.45, 0.85)
    )
    plainness = (
        0.40 * _less_is_better(f["corporate_filler_rate"], 0.5, 4.0)
        + 0.35 * _less_is_better(f["template_phrase_rate"], 0.2, 2.5)
        + 0.25 * _less_is_better(f["booster_rate"], 0.6, 3.0)
    )
    flow = (
        0.40 * _less_is_better(f["adjacent_sentence_overlap"], 0.10, 0.30)
        + 0.30 * _less_is_better(f["repeated_bigram_ratio"], 0.05, 0.18)
        + 0.30 * _band(f["mean_sentence_len"], 11.0, 24.0)
    )
    moderation = (
        0.50 * _band(f["formal_connective_rate"], 0.0, 1.0)
        + 0.25 * _less_is_better(f["anaphoric_opener_rate"], 0.10, 0.35)
        + 0.25 * _less_is_better(f["tricolon_rate"], 0.4, 1.6)
    )
    shape = (
        0.50 * _band(f["paragraph_len_cv"], 0.15, 0.90)
        + 0.50 * _less_is_better(f["uniform_paragraph_size"], 0.55, 0.95)
    )

    report.parts = {
        "variation": variation, "plainness": plainness, "flow": flow,
        "moderation": moderation, "shape": shape,
    }
    total_weight = sum(w for _, w in WEIGHTS)
    report.score = 100.0 * sum(report.parts[k] * w for k, w in WEIGHTS) / total_weight

    if f["sentence_len_cv"] < 0.30:
        report.notes.append("Sentence lengths are very even; the rhythm reads flat.")
    if f["corporate_filler_rate"] > 2.0:
        report.notes.append("Heavy abstract business vocabulary.")
    if f["template_phrase_rate"] > 1.0:
        report.notes.append("Several stock phrases that carry no information.")
    if f["adjacent_sentence_overlap"] > 0.22:
        report.notes.append("Neighbouring sentences restate each other.")
    if f["formal_connective_rate"] > 1.5:
        report.notes.append("Formal connectives are doing too much of the work.")
    if f["opening_diversity"] < 0.6:
        report.notes.append("Many sentences start the same way.")
    return report
