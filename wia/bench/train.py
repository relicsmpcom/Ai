"""Training the detector on HumanBench.

Three things happen here that matter more than the optimiser:

1. **Standardisation stats come from the training split only.**  Feature
   centres and spreads are part of the model, not of the evaluation.
2. **Human examples are weighted up.**  The loss is asymmetric because the
   errors are: labelling a person's own writing as generated is the mistake
   that costs someone a grade or a job.
3. **The decision threshold is fitted, not guessed.**  ``likely_ai`` is set to
   the lowest probability that still holds the false-positive rate on held-out
   human text at or below the target (1% by default).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import wia.features.extractors  # noqa: F401
from wia.bench.dataset import Dataset, Sample
from wia.detector.calibration import DecisionPolicy, fit_temperature
from wia.detector.model import CLASSES, LinearModel, softmax, train as train_linear
from wia.detector.pipeline import WEIGHTS_PATH
from wia.detector.priors import prior_model
from wia.features.doc import Doc
from wia.features.registry import FEATURES, extract, feature_names
from wia.text.tokens import mean, stdev

CLASS_INDEX = {c: i for i, c in enumerate(CLASSES)}


@dataclass
class TrainingReport:
    n_train: int
    n_dev: int
    temperature: float
    policy: DecisionPolicy
    dev_fpr: float
    threshold_source: str
    per_language: Dict[str, int]

    def to_dict(self) -> dict:
        return {
            "n_train": self.n_train,
            "n_dev": self.n_dev,
            "temperature": round(self.temperature, 4),
            "policy": self.policy.to_dict(),
            "dev_false_positive_rate": round(self.dev_fpr, 4),
            "threshold_source": self.threshold_source,
            "per_language": self.per_language,
        }


def featurize(samples: Sequence[Sample]) -> List[Dict[str, float]]:
    return [extract(Doc(s.text, s.language)) for s in samples]


def compute_stats(raw: Sequence[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    """Per-feature centre and spread, with a floor so rare features cannot blow up."""
    stats: Dict[str, Dict[str, float]] = {}
    for f in FEATURES:
        values = [r.get(f.name, 0.0) for r in raw]
        c = mean(values, f.center)
        s = stdev(values, f.spread)
        # A spread far below the prior means this split simply lacks variety;
        # keep the prior so the model does not amplify noise.
        s = max(s, f.spread * 0.35, 1e-6)
        stats[f.name] = {"center": c, "spread": s}
    return stats


def standardize_with(raw: Dict[str, float], stats: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    out = {}
    for f in FEATURES:
        st = stats.get(f.name, {"center": f.center, "spread": f.spread})
        out[f.name] = max(-4.0, min(4.0, (raw.get(f.name, st["center"]) - st["center"]) / (st["spread"] or 1.0)))
    return out


def _fit(
    samples: Sequence[Sample],
    *,
    epochs: int,
    l2: float,
    human_weight: float,
    seed: int,
) -> LinearModel:
    raw = featurize(samples)
    stats = compute_stats(raw)
    X = [standardize_with(r, stats) for r in raw]
    y = [CLASS_INDEX[s.coarse] for s in samples]
    model = train_linear(
        X, y, feature_names(),
        epochs=epochs, l2=l2, seed=seed,
        class_weights=[human_weight, 1.0, 1.0],
        init=prior_model(),
    )
    model.stats = stats
    return model


def fit_threshold_for_fpr(
    negative_scores: Sequence[float], target_fpr: float, floor: float
) -> Tuple[float, float]:
    """Lowest threshold whose false-positive rate on human text stays under target.

    ``floor`` is a hard conservative bound: no amount of clean-looking held-out
    data may push a threshold below it, because a threshold fitted on a few
    hundred documents is an estimate, not a guarantee.
    """
    if not negative_scores:
        return floor, float("nan")
    ordered = sorted(negative_scores, reverse=True)
    allowed = int(len(ordered) * target_fpr)
    thr = ordered[allowed] + 1e-6 if allowed < len(ordered) else floor
    thr = max(floor, min(0.99, thr))
    fpr = sum(1 for p in negative_scores if p >= thr) / len(negative_scores)
    return thr, fpr


def fit_policy(
    samples: Sequence[Sample],
    temperature: float,
    *,
    target_fpr: float = 0.01,
    folds: int = 5,
    **fit_kw,
) -> Tuple[DecisionPolicy, float, str]:
    """Fit the decision thresholds on out-of-fold probabilities."""
    from wia.bench.dataset import Dataset as _Dataset

    oof_probs: List[List[float]] = []
    oof_labels: List[int] = []
    for held, model in cross_validate(_Dataset(samples), folds=folds, **fit_kw):
        model.temperature = temperature
        oof_probs.extend(_pipeline_probabilities(held, model, {}))
        oof_labels.extend(CLASS_INDEX[s.coarse] for s in held)

    human_ai = [p[2] for p, y in zip(oof_probs, oof_labels) if y == 0]
    human_mixed = [p[1] for p, y in zip(oof_probs, oof_labels) if y == 0]

    likely_ai, fpr = fit_threshold_for_fpr(human_ai, target_fpr, floor=0.70)
    mostly_ai, _ = fit_threshold_for_fpr(human_ai, min(0.05, target_fpr * 5), floor=0.55)
    mixed_floor, _ = fit_threshold_for_fpr(human_mixed, 0.08, floor=0.34)

    policy = DecisionPolicy(
        likely_ai=round(likely_ai, 4),
        mostly_ai=round(min(mostly_ai, likely_ai - 0.05), 4),
        mixed_floor=round(mixed_floor, 4),
    )
    source = (
        f"fitted on {len(oof_labels)} out-of-fold predictions "
        f"({len(human_ai)} human) at target FPR {target_fpr:.0%}, "
        f"with conservative floors"
    )
    return policy, fpr, source


def train_detector(
    dataset: Optional[Dataset] = None,
    *,
    out_path: Optional[Path] = None,
    epochs: int = 500,
    l2: float = 0.12,
    human_weight: float = 2.0,
    target_fpr: float = 0.01,
    seed: int = 11,
) -> TrainingReport:
    ds = (dataset or Dataset.load()).trainable()
    train = list(ds.split_by("train"))
    dev = list(ds.split_by("dev"))
    if not train:
        raise SystemExit("no training samples found")

    global_model = _fit(train, epochs=epochs, l2=l2, human_weight=human_weight, seed=seed)

    by_language: Dict[str, LinearModel] = {}
    counts: Dict[str, int] = {}
    for lang in ("nl", "en"):
        subset = [s for s in train if s.language == lang]
        counts[lang] = len(subset)
        # Per-language models only earn their place once there is enough data;
        # below that the global model generalises better.
        if len(subset) >= 40:
            by_language[lang] = _fit(
                subset, epochs=epochs, l2=l2 * 1.3, human_weight=human_weight, seed=seed + 1
            )

    # --- calibration on dev -------------------------------------------------
    # Calibration is fitted on the probabilities the *product* reports, after
    # shrinkage and hard-negative damping — not on the raw logits.  Calibrating
    # a number nobody sees would be theatre.
    temperature = 1.0
    dev_fpr = float("nan")
    policy = DecisionPolicy()
    threshold_source = "default (no dev split)"
    if dev:
        labels = [CLASS_INDEX[s.coarse] for s in dev]
        temperature = _fit_temperature_on_pipeline(
            dev, labels, global_model, by_language
        )
        global_model.temperature = temperature
        for m in by_language.values():
            m.temperature = temperature

        # Thresholds are fitted on out-of-fold predictions over train+dev, not
        # on the dev split alone: with thirty documents an "FPR of 0%" says
        # nothing, and fitting on data the model was trained on says less.
        policy, dev_fpr, threshold_source = fit_policy(
            list(train) + list(dev), temperature, target_fpr=target_fpr,
            epochs=epochs, l2=l2, human_weight=human_weight, seed=seed,
        )

    blob = {
        "global": global_model.to_dict(),
        "by_language": {k: v.to_dict() for k, v in by_language.items()},
        "policy": policy.to_dict(),
        "meta": {
            "trained": True,
            "n_train": len(train),
            "n_dev": len(dev),
            "epochs": epochs,
            "l2": l2,
            "human_weight": human_weight,
            "target_fpr": target_fpr,
            "corpus": "HumanBench-NL/EN seed",
        },
    }
    path = Path(out_path or WEIGHTS_PATH)
    path.write_text(json.dumps(blob, indent=1), encoding="utf-8")

    return TrainingReport(
        n_train=len(train), n_dev=len(dev), temperature=temperature, policy=policy,
        dev_fpr=dev_fpr, threshold_source=threshold_source, per_language=counts,
    )


def _pipeline_probabilities(
    samples: Sequence[Sample],
    global_model: LinearModel,
    by_language: Dict[str, LinearModel],
) -> List[List[float]]:
    """Final, delivered probabilities for each sample (same path as inference)."""
    from wia.detector.pipeline import Detector

    det = Detector(model=global_model, models_by_language=by_language)
    out = []
    for s in samples:
        r = det.detect(s.text, language=s.language, with_segments=False)
        out.append([r.human_probability, r.mixed_probability, r.ai_probability])
    return out


def _fit_temperature_on_pipeline(
    samples: Sequence[Sample],
    labels: Sequence[int],
    global_model: LinearModel,
    by_language: Dict[str, LinearModel],
    candidates: Sequence[float] = tuple(x / 20 for x in range(6, 121, 2)),
) -> float:
    """Pick the temperature whose *delivered* probabilities minimise NLL."""
    import math

    best_t, best = 1.0, float("inf")
    for t in candidates:
        global_model.temperature = t
        for m in by_language.values():
            m.temperature = t
        probs = _pipeline_probabilities(samples, global_model, by_language)
        nll = -sum(math.log(max(1e-9, p[y])) for p, y in zip(probs, labels)) / len(labels)
        if nll < best:
            best, best_t = nll, t
    return best_t


def cross_validate(
    dataset: Optional[Dataset] = None, folds: int = 5, seed: int = 3, **kw
) -> List[Tuple[List[Sample], LinearModel]]:
    """K-fold models for honest reporting on a corpus this small."""
    ds = (dataset or Dataset.load()).trainable()
    samples = list(ds)
    rng = random.Random(seed)
    rng.shuffle(samples)
    buckets: List[List[Sample]] = [[] for _ in range(folds)]
    # Stratify by coarse class so every fold has human, mixed and AI examples.
    for cls in CLASSES:
        subset = [s for s in samples if s.coarse == cls]
        for i, s in enumerate(subset):
            buckets[i % folds].append(s)
    out = []
    for i in range(folds):
        held = buckets[i]
        rest = [s for j, b in enumerate(buckets) if j != i for s in b]
        model = _fit(
            rest,
            epochs=kw.get("epochs", 400),
            l2=kw.get("l2", 0.12),
            human_weight=kw.get("human_weight", 2.0),
            seed=seed + i,
        )
        out.append((held, model))
    return out
