"""Bootstrap weights derived from feature *direction* metadata.

The platform must behave sensibly before anyone has collected a single
labelled document — otherwise there is no way to look at data collection
decisions and no baseline for the trained model to beat.  These priors are
weak on purpose: every direction gets the same modest weight, so no single
feature can carry a verdict, and training is expected to replace them.
"""

from __future__ import annotations

from wia.detector.model import LinearModel
from wia.features.registry import FEATURES, feature_names

PRIOR_WEIGHT = 0.22


def prior_model() -> LinearModel:
    m = LinearModel(feature_names=feature_names())
    for f in FEATURES:
        if f.direction == "ai":
            m.weights[f.name] = [-PRIOR_WEIGHT, 0.0, PRIOR_WEIGHT]
        elif f.direction == "human":
            m.weights[f.name] = [PRIOR_WEIGHT, 0.0, -PRIOR_WEIGHT]
        else:
            m.weights[f.name] = [0.0, 0.0, 0.0]
    # Start biased toward "human": in the absence of evidence the conservative
    # answer is that a person wrote it.
    m.bias = [0.85, 0.15, -0.35]
    m.temperature = 2.6  # priors are over-confident; flatten them hard
    m.meta = {"kind": "prior", "trained": False}
    return m
