"""A small, dependency-free multinomial logistic model.

Why not a transformer?  A transformer belongs in this system — the roadmap
puts one in the ensemble and this package leaves a slot for it — but the
measurement layer has to exist first, has to run in milliseconds on CPU, and
has to be inspectable when it makes a mistake.  A linear model over named
features is all three, and it is the honest baseline every stronger model has
to beat on HumanBench before it ships.

Classes are fixed and ordered: ``human``, ``mixed``, ``ai``.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

CLASSES: Tuple[str, str, str] = ("human", "mixed", "ai")


def softmax(scores: Sequence[float]) -> List[float]:
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    total = sum(exps) or 1.0
    return [e / total for e in exps]


@dataclass
class LinearModel:
    feature_names: List[str]
    weights: Dict[str, List[float]] = field(default_factory=dict)  # feature -> per-class
    bias: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    stats: Dict[str, Dict[str, float]] = field(default_factory=dict)
    temperature: float = 1.0
    meta: Dict[str, object] = field(default_factory=dict)

    # -- inference ---------------------------------------------------------
    def scores(self, z: Dict[str, float]) -> List[float]:
        out = list(self.bias)
        for name in self.feature_names:
            v = z.get(name, 0.0)
            if v == 0.0:
                continue
            w = self.weights.get(name)
            if not w:
                continue
            for c in range(3):
                out[c] += w[c] * v
        return out

    def predict(self, z: Dict[str, float]) -> List[float]:
        s = self.scores(z)
        t = self.temperature or 1.0
        return softmax([x / t for x in s])

    # -- persistence -------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "classes": list(CLASSES),
            "feature_names": self.feature_names,
            "weights": {k: [round(x, 6) for x in v] for k, v in self.weights.items()},
            "bias": [round(x, 6) for x in self.bias],
            "stats": {
                k: {kk: round(vv, 6) for kk, vv in v.items()}
                for k, v in self.stats.items()
            },
            "temperature": round(self.temperature, 6),
            "meta": self.meta,
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: dict) -> "LinearModel":
        return cls(
            feature_names=list(d["feature_names"]),
            weights={k: list(v) for k, v in d.get("weights", {}).items()},
            bias=list(d.get("bias", [0.0, 0.0, 0.0])),
            stats={k: dict(v) for k, v in d.get("stats", {}).items()},
            temperature=float(d.get("temperature", 1.0)),
            meta=dict(d.get("meta", {})),
        )

    @classmethod
    def load(cls, path: str | Path) -> "LinearModel":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def train(
    X: List[Dict[str, float]],
    y: List[int],
    feature_names: List[str],
    *,
    epochs: int = 400,
    lr: float = 0.15,
    l2: float = 0.03,
    sample_weights: Optional[List[float]] = None,
    class_weights: Optional[Sequence[float]] = None,
    seed: int = 7,
    init: Optional[LinearModel] = None,
) -> LinearModel:
    """Batch gradient descent on the multinomial cross-entropy.

    ``class_weights`` exists for one reason: the cost of the three mistakes is
    not symmetric.  Calling a human writer AI is the failure that damages
    people, so human examples are allowed to weigh more than AI examples.
    """
    rng = random.Random(seed)
    model = LinearModel(feature_names=list(feature_names))
    if init is not None:
        model.weights = {k: list(v) for k, v in init.weights.items()}
        model.bias = list(init.bias)
        model.stats = dict(init.stats)
    for name in feature_names:
        model.weights.setdefault(name, [rng.uniform(-0.01, 0.01) for _ in range(3)])

    n = len(X)
    if n == 0:
        return model
    sw = list(sample_weights) if sample_weights else [1.0] * n
    cw = list(class_weights) if class_weights else [1.0, 1.0, 1.0]
    total_w = sum(sw[i] * cw[y[i]] for i in range(n)) or 1.0

    for epoch in range(epochs):
        grad_w = {name: [0.0, 0.0, 0.0] for name in feature_names}
        grad_b = [0.0, 0.0, 0.0]
        for i in range(n):
            probs = softmax(model.scores(X[i]))
            w_i = sw[i] * cw[y[i]]
            err = [probs[c] - (1.0 if y[i] == c else 0.0) for c in range(3)]
            for c in range(3):
                e = err[c] * w_i
                if e == 0.0:
                    continue
                grad_b[c] += e
                xi = X[i]
                for name in feature_names:
                    v = xi.get(name, 0.0)
                    if v:
                        grad_w[name][c] += e * v
        step = lr * (0.5 ** (epoch / max(1, epochs / 3)))  # simple decay
        for c in range(3):
            model.bias[c] -= step * grad_b[c] / total_w
        for name in feature_names:
            w = model.weights[name]
            g = grad_w[name]
            for c in range(3):
                w[c] -= step * (g[c] / total_w + l2 * w[c])
    return model
