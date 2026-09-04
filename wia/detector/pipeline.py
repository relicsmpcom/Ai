"""The detector pipeline.

    text
      ├─ language identification
      ├─ domain classification
      ├─ feature extraction (51 measurements)
      ├─ linear ensemble over standardised features
      ├─ short-text shrinkage
      ├─ hard-negative damping
      ├─ calibration (temperature) + decision policy
      ├─ windowed segment analysis  → heatmap
      └─ mixed-authorship summary

Every stage can be inspected from the outside, and every number that reaches
the user is a probability with a stated confidence — never a verdict.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import wia.features.extractors  # noqa: F401  (registers the feature battery)
from wia.detector.calibration import DecisionPolicy, shrink_toward_human
from wia.detector.domain import classify_domain
from wia.detector.model import CLASSES, LinearModel
from wia.detector.priors import prior_model
from wia.detector.risk import RiskFactor, assess, dampen
from wia.features.doc import Doc
from wia.features.registry import FEATURES, extract, get_feature, standardize
from wia.text.segment import windows
from wia.lang import detect_language
from wia.types import (
    AuthorshipClass,
    Confidence,
    DetectionResult,
    Language,
    SegmentResult,
)

WEIGHTS_PATH = Path(__file__).with_name("weights.json")


class Detector:
    """Authorship estimation for Dutch and English."""

    def __init__(
        self,
        model: Optional[LinearModel] = None,
        policy: Optional[DecisionPolicy] = None,
        models_by_language: Optional[Dict[str, LinearModel]] = None,
    ) -> None:
        self.model = model or prior_model()
        self.policy = policy or DecisionPolicy()
        self.models_by_language = models_by_language or {}

    # -- construction ------------------------------------------------------
    @classmethod
    def load(cls, path: Optional[str | Path] = None) -> "Detector":
        """Load trained weights when they exist, fall back to priors."""
        p = Path(path) if path else WEIGHTS_PATH
        if not p.exists():
            return cls()
        import json

        blob = json.loads(p.read_text(encoding="utf-8"))
        base = LinearModel.from_dict(blob["global"] if "global" in blob else blob)
        base.meta = {**base.meta, **(blob.get("meta") or {})}
        per_lang = {
            lang: LinearModel.from_dict(m)
            for lang, m in (blob.get("by_language") or {}).items()
        }
        policy = DecisionPolicy.from_dict(blob.get("policy", {}))
        return cls(base, policy, per_lang)

    def model_for(self, language: Language) -> LinearModel:
        return self.models_by_language.get(language.value, self.model)

    # -- inference ---------------------------------------------------------
    def detect(
        self,
        text: str,
        language: str = "auto",
        *,
        with_segments: bool = True,
        domain: Optional[str] = None,
    ) -> DetectionResult:
        text = text or ""
        guess = detect_language(text)
        lang = Language.parse(language) if language not in (None, "", "auto") else guess.language
        lang_conf = guess.confidence if lang is guess.language else 0.99
        if lang is Language.UNKNOWN:
            # Fall back to the English feature set; say so in the warnings.
            lang = Language.EN if guess.en_score >= guess.nl_score else Language.NL

        doc = Doc(text, lang.value)
        raw = extract(doc)
        model = self.model_for(lang)
        z = standardize(raw, model.stats)
        probs = model.predict(z)

        dom, dom_conf = (domain, 1.0) if domain else classify_domain(text)

        probs = shrink_toward_human(probs, doc.n_words)
        factors = assess(doc, raw)
        probs = dampen(probs, factors)
        total = sum(probs) or 1.0
        p_human, p_mixed, p_ai = [p / total for p in probs]

        label, confidence = self.policy.decide(p_human, p_mixed, p_ai, doc.n_words)

        segments: List[SegmentResult] = []
        mixed_summary: Dict[str, object] = {}
        if with_segments and doc.n_words >= 60:
            segments = self._segment_scores(text, lang, model)
            mixed_summary = summarize_mixed(segments)
            # A text whose spans disagree strongly is mixed authorship even if
            # the document-level model split the difference.  This needs at
            # least three windows to mean anything — two windows disagreeing
            # is just short-text noise.
            if (
                mixed_summary.get("segment_count", 0) >= 3
                and mixed_summary.get("disagreement", 0.0) > 0.35
                and label in (AuthorshipClass.MOSTLY_HUMAN, AuthorshipClass.MOSTLY_AI)
            ):
                label = AuthorshipClass.MIXED

        result = DetectionResult(
            language=lang,
            language_confidence=lang_conf,
            human_probability=p_human,
            mixed_probability=p_mixed,
            ai_probability=p_ai,
            label=label,
            confidence=confidence,
            words=doc.n_words,
            segments=segments,
            mixed_authorship=mixed_summary,
            features=raw,
            domain=dom,
        )
        result.explanations = explain(z, model, (p_human, p_mixed, p_ai))
        result.warnings = [f.message for f in factors]
        if guess.language is Language.UNKNOWN and language in (None, "", "auto"):
            result.warnings.insert(
                0,
                "Language could not be identified with confidence; analysed as "
                f"{lang.value.upper()}. Results on other languages are not supported.",
            )
        if dom_conf < 0.3:
            result.domain = "general"
        return result

    def _segment_scores(
        self, text: str, lang: Language, model: LinearModel
    ) -> List[SegmentResult]:
        out: List[SegmentResult] = []
        for seg in windows(text, target_words=60, stride_words=30):
            sdoc = Doc(seg.text, lang.value)
            raw = extract(sdoc)
            z = standardize(raw, model.stats)
            probs = model.predict(z)
            probs = shrink_toward_human(probs, sdoc.n_words, floor_words=90, strength=0.6)
            probs = dampen(probs, [f for f in assess(sdoc, raw) if f.key != "short_text"])
            total = sum(probs) or 1.0
            ph, pm, pa = [p / total for p in probs]
            label, conf = self.policy.decide(ph, pm, pa, max(sdoc.n_words, 40))
            out.append(
                SegmentResult(
                    segment=seg,
                    human_probability=ph,
                    mixed_probability=pm,
                    ai_probability=pa,
                    label=label,
                    confidence=conf,
                    reliability=min(1.0, sdoc.n_words / 80.0),
                )
            )
        return out


def summarize_mixed(segments: List[SegmentResult]) -> Dict[str, object]:
    """Describe how the estimate varies across the document."""
    if not segments:
        return {}
    weights = [max(1e-6, s.reliability) * s.segment.length for s in segments]
    total_w = sum(weights) or 1.0
    ai = sum(w * s.ai_probability for w, s in zip(weights, segments)) / total_w
    human = sum(w * s.human_probability for w, s in zip(weights, segments)) / total_w
    ai_values = [s.ai_probability for s in segments]
    spread = max(ai_values) - min(ai_values)
    switches = sum(
        1
        for a, b in zip(ai_values, ai_values[1:])
        if (a >= 0.5) != (b >= 0.5)
    )
    ai_span_share = sum(
        s.segment.length for s in segments if s.ai_probability >= 0.55
    ) / max(1, sum(s.segment.length for s in segments))
    return {
        "segment_count": len(segments),
        "weighted_ai_probability": round(ai, 4),
        "weighted_human_probability": round(human, 4),
        "ai_span_share": round(ai_span_share, 4),
        "disagreement": round(spread, 4),
        "switches": switches,
        "verdict": (
            "consistent" if spread < 0.20
            else "uneven" if spread < 0.35
            else "mixed authorship likely"
        ),
    }


def explain(
    z: Dict[str, float], model: LinearModel, probs, top_k: int = 6
) -> List[str]:
    """Name the measurements that moved this particular estimate.

    Contribution is ``weight × standardised value`` for the winning class, so
    the explanation reflects what the model actually did, not a story told
    afterwards.
    """
    winner = max(range(3), key=lambda i: probs[i])
    contributions = []
    for name, value in z.items():
        w = model.weights.get(name)
        if not w:
            continue
        contributions.append((w[winner] * value, name, value))
    contributions.sort(key=lambda t: abs(t[0]), reverse=True)

    lines: List[str] = []
    for contrib, name, value in contributions[:top_k]:
        if abs(contrib) < 0.02:
            continue
        try:
            f = get_feature(name)
        except KeyError:
            continue
        direction = "supports" if contrib > 0 else "argues against"
        level = "unusually high" if value > 0.8 else "unusually low" if value < -0.8 else "typical"
        lines.append(
            f"{f.doc.split('.')[0]} — {level} for this length "
            f"({direction} “{CLASSES[winner]}”)."
        )
    if not lines:
        lines.append(
            "No individual measurement stands out; the estimate comes from the "
            "combination of many weak signals."
        )
    return lines
