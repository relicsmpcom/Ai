"""The feature registry.

Every feature is declared with the metadata the rest of the platform needs:

* ``center`` / ``spread`` — a prior standardisation, so an untrained detector
  still produces sane numbers and a trained one starts from a good scale;
* ``direction`` — which way the feature *tends* to point (``"ai"`` or
  ``"human"``), used for human-readable explanations only, never as a rule;
* ``doc`` — the sentence shown in the UI when this feature is cited.

No feature is a decision on its own.  The detector sees the whole vector.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from wia.features.doc import Doc


@dataclass(frozen=True)
class Feature:
    name: str
    group: str
    doc: str
    fn: Callable[[Doc], float]
    center: float
    spread: float
    direction: Optional[str] = None  # "ai" | "human" | None

    def value(self, d: Doc) -> float:
        try:
            v = float(self.fn(d))
        except ZeroDivisionError:
            v = 0.0
        if v != v or v in (float("inf"), float("-inf")):  # NaN / inf guard
            v = 0.0
        return v

    def z(self, value: float) -> float:
        return (value - self.center) / (self.spread or 1.0)


FEATURES: List[Feature] = []
_BY_NAME: Dict[str, Feature] = {}


def feature(name: str, group: str, doc: str, center: float, spread: float,
            direction: Optional[str] = None):
    def deco(fn: Callable[[Doc], float]) -> Callable[[Doc], float]:
        f = Feature(name, group, doc, fn, center, spread, direction)
        FEATURES.append(f)
        _BY_NAME[name] = f
        return fn

    return deco


def get_feature(name: str) -> Feature:
    return _BY_NAME[name]


def feature_names() -> List[str]:
    return [f.name for f in FEATURES]


def extract(doc: Doc) -> Dict[str, float]:
    """Raw feature values for a document."""
    return {f.name: f.value(doc) for f in FEATURES}


def standardize(values: Dict[str, float],
                stats: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, float]:
    """Z-score features using trained stats when available, priors otherwise."""
    out: Dict[str, float] = {}
    for f in FEATURES:
        v = values.get(f.name, f.center)
        if stats and f.name in stats:
            c = stats[f.name].get("center", f.center)
            s = stats[f.name].get("spread", f.spread) or f.spread
        else:
            c, s = f.center, f.spread
        out[f.name] = max(-4.0, min(4.0, (v - c) / (s or 1.0)))
    return out
