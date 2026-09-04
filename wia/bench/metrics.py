"""Evaluation metrics.

Accuracy is banned from this module's vocabulary as a headline number.  The
metrics that decide whether a detector may ship are the ones that describe
what happens to innocent writers: true-positive rate measured *at a fixed
false-positive rate*, and calibration error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from wia.detector.calibration import expected_calibration_error, reliability_table


def roc_points(scores: Sequence[float], labels: Sequence[int]) -> List[Tuple[float, float, float]]:
    """Return ``(fpr, tpr, threshold)`` points, high threshold first."""
    pairs = sorted(zip(scores, labels), key=lambda t: -t[0])
    P = sum(1 for _, y in pairs if y == 1)
    N = len(pairs) - P
    if P == 0 or N == 0:
        return []
    tp = fp = 0
    out = [(0.0, 0.0, float("inf"))]
    prev: Optional[float] = None
    for s, y in pairs:
        if prev is not None and s != prev:
            out.append((fp / N, tp / P, prev))
        tp += y == 1
        fp += y == 0
        prev = s
    out.append((fp / N, tp / P, prev if prev is not None else 0.0))
    return out


def roc_auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Rank-based AUC (ties handled by average rank)."""
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return float("nan")
    ordered = sorted(zip(scores, labels), key=lambda t: t[0])
    ranks: Dict[int, float] = {}
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][0] == ordered[i][0]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    rank_sum = sum(ranks[k] for k, (_, y) in enumerate(ordered) if y == 1)
    n_pos, n_neg = len(pos), len(neg)
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def tpr_at_fpr(
    scores: Sequence[float], labels: Sequence[int], target_fpr: float
) -> Tuple[float, float]:
    """Best TPR achievable without exceeding ``target_fpr``.

    Returns ``(tpr, threshold)``.  This is the number that governs whether a
    detector is safe to point at a real person's work.
    """
    pts = roc_points(scores, labels)
    if not pts:
        return float("nan"), float("nan")
    best = (0.0, float("inf"))
    for fpr, tpr, thr in pts:
        if fpr <= target_fpr + 1e-12 and tpr >= best[0]:
            best = (tpr, thr)
    return best


def prf(
    predicted: Sequence[str], actual: Sequence[str], positive: str
) -> Dict[str, float]:
    tp = sum(1 for p, a in zip(predicted, actual) if p == positive and a == positive)
    fp = sum(1 for p, a in zip(predicted, actual) if p == positive and a != positive)
    fn = sum(1 for p, a in zip(predicted, actual) if p != positive and a == positive)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn}


def confusion(predicted: Sequence[str], actual: Sequence[str],
              classes: Sequence[str]) -> Dict[str, Dict[str, int]]:
    m = {a: {p: 0 for p in classes} for a in classes}
    for p, a in zip(predicted, actual):
        if a in m and p in m[a]:
            m[a][p] += 1
    return m


@dataclass
class EvalResult:
    n: int = 0
    roc_auc_ai: float = float("nan")
    tpr_at_1pct_fpr: float = float("nan")
    tpr_at_5pct_fpr: float = float("nan")
    threshold_1pct: float = float("nan")
    threshold_5pct: float = float("nan")
    ece: float = float("nan")
    macro_f1: float = float("nan")
    per_class: Dict[str, Dict[str, float]] = field(default_factory=dict)
    confusion: Dict[str, Dict[str, int]] = field(default_factory=dict)
    reliability: List[Dict[str, float]] = field(default_factory=list)
    false_positive_rate: float = float("nan")
    human_accused_rate: float = float("nan")
    uncertain_rate: float = float("nan")
    slices: Dict[str, Dict[str, Dict[str, float]]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        return d


def evaluate(
    *,
    ai_scores: Sequence[float],
    is_ai: Sequence[int],
    predicted: Sequence[str],
    actual: Sequence[str],
    top_prob: Sequence[float],
    classes: Sequence[str] = ("human", "mixed", "ai"),
) -> EvalResult:
    """Core evaluation over one set of predictions."""
    res = EvalResult(n=len(actual))
    res.roc_auc_ai = roc_auc(ai_scores, is_ai)
    res.tpr_at_1pct_fpr, res.threshold_1pct = tpr_at_fpr(ai_scores, is_ai, 0.01)
    res.tpr_at_5pct_fpr, res.threshold_5pct = tpr_at_fpr(ai_scores, is_ai, 0.05)
    correct = [1 if p == a else 0 for p, a in zip(predicted, actual)]
    res.ece = expected_calibration_error(top_prob, correct)
    res.reliability = reliability_table(top_prob, correct)
    res.per_class = {c: prf(predicted, actual, c) for c in classes}
    res.macro_f1 = sum(res.per_class[c]["f1"] for c in classes) / len(classes)
    res.confusion = confusion(predicted, actual, list(classes) + ["uncertain"])

    humans = [i for i, a in enumerate(actual) if a == "human"]
    if humans:
        res.false_positive_rate = sum(
            1 for i in humans if predicted[i] == "ai"
        ) / len(humans)
        res.human_accused_rate = sum(
            1 for i in humans if predicted[i] in ("ai", "mixed")
        ) / len(humans)
    res.uncertain_rate = sum(1 for p in predicted if p == "uncertain") / max(1, len(predicted))
    return res
