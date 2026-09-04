"""Running the benchmark and rendering the report.

The report deliberately leads with the numbers that describe harm — the
false-positive rate and what happens on the hard-negative slice — and only
then shows discrimination and calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from wia.bench.dataset import Dataset, Sample
from wia.bench.metrics import EvalResult, evaluate
from wia.bench.train import cross_validate
from wia.detector.pipeline import Detector
from wia.types import AuthorshipClass

COARSE_FROM_LABEL = {
    AuthorshipClass.LIKELY_HUMAN: "human",
    AuthorshipClass.MOSTLY_HUMAN: "human",
    AuthorshipClass.MIXED: "mixed",
    AuthorshipClass.MOSTLY_AI: "ai",
    AuthorshipClass.LIKELY_AI: "ai",
    AuthorshipClass.UNCERTAIN: "uncertain",
}


@dataclass
class Prediction:
    sample_id: str
    language: str
    domain: str
    bucket: str
    provenance: str
    hard_negative: bool
    actual: str
    predicted: str
    ai_probability: float
    top_probability: float
    words: int

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def predict(detector: Detector, samples: Sequence[Sample]) -> List[Prediction]:
    out: List[Prediction] = []
    for s in samples:
        # Segments on: the benchmark must exercise the same path the product
        # uses, including the segment-disagreement route into "mixed".
        r = detector.detect(s.text, language=s.language, with_segments=True)
        out.append(Prediction(
            sample_id=s.id,
            language=s.language,
            domain=s.domain,
            bucket=s.bucket,
            provenance=s.provenance,
            hard_negative="hard_negative" in s.tags,
            actual=s.coarse or "uncertain",
            predicted=COARSE_FROM_LABEL[r.label],
            ai_probability=r.ai_probability,
            top_probability=max(r.human_probability, r.mixed_probability, r.ai_probability),
            words=r.words,
        ))
    return out


def _score(preds: Sequence[Prediction]) -> EvalResult:
    return evaluate(
        ai_scores=[p.ai_probability for p in preds],
        is_ai=[1 if p.actual == "ai" else 0 for p in preds],
        predicted=[p.predicted for p in preds],
        actual=[p.actual for p in preds],
        top_prob=[p.top_probability for p in preds],
    )


def _slice_scores(preds: Sequence[Prediction], key) -> Dict[str, Dict[str, float]]:
    groups: Dict[str, List[Prediction]] = {}
    for p in preds:
        groups.setdefault(key(p), []).append(p)
    out: Dict[str, Dict[str, float]] = {}
    for name, group in sorted(groups.items()):
        r = _score(group)
        out[name] = {
            "n": r.n,
            "macro_f1": r.macro_f1,
            "roc_auc_ai": r.roc_auc_ai,
            "false_positive_rate": r.false_positive_rate,
            "uncertain_rate": r.uncertain_rate,
        }
    return out


def run_eval(
    *,
    split: Optional[str] = "test",
    detector: Optional[Detector] = None,
    dataset: Optional[Dataset] = None,
) -> dict:
    ds = (dataset or Dataset.load()).trainable()
    samples = list(ds.split_by(split)) if split else list(ds)
    det = detector or Detector.load()
    preds = predict(det, samples)
    result = _score(preds)
    result.slices = {
        "language": _slice_scores(preds, lambda p: p.language),
        "length": _slice_scores(preds, lambda p: p.bucket),
        "domain": _slice_scores(preds, lambda p: p.domain),
        "provenance": _slice_scores(preds, lambda p: p.provenance),
    }
    hard = [p for p in preds if p.hard_negative]
    return {
        "split": split or "all",
        "n": len(preds),
        "metrics": result.to_dict(),
        "hard_negatives": {
            "n": len(hard),
            "accused_as_ai": sum(1 for p in hard if p.predicted == "ai"),
            "accused_as_mixed": sum(1 for p in hard if p.predicted == "mixed"),
            "held_as_human_or_uncertain": sum(
                1 for p in hard if p.predicted in ("human", "uncertain")
            ),
            "cases": [p.to_dict() for p in hard if p.predicted in ("ai", "mixed")],
        },
        "predictions": [p.to_dict() for p in preds],
    }


def run_cross_validation(folds: int = 5, dataset: Optional[Dataset] = None) -> dict:
    """Out-of-fold evaluation — the honest headline on a corpus this small."""
    policy = Detector.load().policy
    all_preds: List[Prediction] = []
    for held, model in cross_validate(dataset, folds=folds):
        det = Detector(model=model, policy=policy)
        all_preds.extend(predict(det, held))
    result = _score(all_preds)
    result.slices = {
        "language": _slice_scores(all_preds, lambda p: p.language),
        "length": _slice_scores(all_preds, lambda p: p.bucket),
    }
    hard = [p for p in all_preds if p.hard_negative]
    return {
        "split": f"{folds}-fold cross-validation (out of fold)",
        "n": len(all_preds),
        "metrics": result.to_dict(),
        "hard_negatives": {
            "n": len(hard),
            "accused_as_ai": sum(1 for p in hard if p.predicted == "ai"),
            "accused_as_mixed": sum(1 for p in hard if p.predicted == "mixed"),
            "held_as_human_or_uncertain": sum(
                1 for p in hard if p.predicted in ("human", "uncertain")
            ),
            "cases": [p.to_dict() for p in hard if p.predicted in ("ai", "mixed")],
        },
    }


def _fmt(v) -> str:
    if isinstance(v, float):
        if v != v:
            return "n/a"
        return f"{v:.3f}"
    return str(v)


def render_markdown(report: dict) -> str:
    m = report["metrics"]
    lines = [
        f"# Detector evaluation — {report['split']}",
        "",
        f"Samples: **{report['n']}**",
        "",
        "## Safety first",
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| False-positive rate (human called AI) | {_fmt(m['false_positive_rate'])} |",
        f"| Human text called AI *or* mixed | {_fmt(m['human_accused_rate'])} |",
        f"| TPR @ 1% FPR | {_fmt(m['tpr_at_1pct_fpr'])} |",
        f"| TPR @ 5% FPR | {_fmt(m['tpr_at_5pct_fpr'])} |",
        f"| Answers withheld as uncertain | {_fmt(m['uncertain_rate'])} |",
        "",
        "## Discrimination and calibration",
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| ROC-AUC (AI vs rest) | {_fmt(m['roc_auc_ai'])} |",
        f"| Macro F1 | {_fmt(m['macro_f1'])} |",
        f"| Expected calibration error | {_fmt(m['ece'])} |",
        "",
        "## Per class",
        "",
        "| class | precision | recall | F1 | n |",
        "| --- | --- | --- | --- | --- |",
    ]
    for cls, pc in m["per_class"].items():
        n = pc["tp"] + pc["fn"]
        lines.append(
            f"| {cls} | {_fmt(pc['precision'])} | {_fmt(pc['recall'])} | {_fmt(pc['f1'])} | {n} |"
        )

    hn = report.get("hard_negatives") or {}
    if hn.get("n"):
        lines += [
            "",
            "## Hard negatives",
            "",
            "Human writing chosen because it *looks* generated: non-native writers, "
            "legal and policy prose, plain-language public information, translated "
            "text, grammar-checked writing.",
            "",
            f"- samples: **{hn['n']}**",
            f"- wrongly called AI: **{hn['accused_as_ai']}**",
            f"- called mixed: **{hn['accused_as_mixed']}**",
            f"- held as human or uncertain: **{hn['held_as_human_or_uncertain']}**",
        ]
        for case in hn.get("cases", []):
            lines.append(
                f"  - `{case['sample_id']}` ({case['language']}, {case['domain']}, "
                f"{case['words']}w) → {case['predicted']} "
                f"(p_ai={case['ai_probability']:.2f})"
            )

    for axis, rows in (m.get("slices") or {}).items():
        lines += ["", f"## By {axis}", "",
                  "| slice | n | macro F1 | ROC-AUC | FPR | uncertain |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for name, r in rows.items():
            lines.append(
                f"| {name} | {r['n']} | {_fmt(r['macro_f1'])} | {_fmt(r['roc_auc_ai'])} "
                f"| {_fmt(r['false_positive_rate'])} | {_fmt(r['uncertain_rate'])} |"
            )
    lines += ["", "## Confusion (rows = actual)", "",
              "| actual \\ predicted | human | mixed | ai | uncertain |",
              "| --- | --- | --- | --- | --- |"]
    for actual, row in m["confusion"].items():
        lines.append(
            f"| {actual} | {row.get('human', 0)} | {row.get('mixed', 0)} "
            f"| {row.get('ai', 0)} | {row.get('uncertain', 0)} |"
        )
    return "\n".join(lines) + "\n"
