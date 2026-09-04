"""The humanizer.

    input
      ├─ language + style analysis
      ├─ plan (what is actually wrong with this text)
      ├─ protect anchors (quotes, URLs, code, reference numbers)
      ├─ candidates A / B / C at three intensities
      │    └─ multi-pass operations
      ├─ critics: meaning, naturalness, grammar, style, tone, locale
      ├─ reject anything that moved a fact — then retry it gently
      └─ ranked candidates with scores and a change log

What it will not do: invent experiences, add facts, change numbers, or
optimise against the detector.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from wia.humanizer.context import Context
from wia.humanizer.critics import QualityScore, score_rewrite
from wia.humanizer.options import HumanizeOptions
from wia.humanizer.ops import OPS, run_ops
from wia.humanizer.plan import Plan, build_plan
from wia.humanizer.style_dna import StyleProfile
from wia.lang import detect_language
from wia.types import Language, Locale

#: A = safest, B = most natural, C = strongest style adaptation (roadmap §15).
CANDIDATE_SPECS = (
    ("A", "Closest to your original", 0.45),
    ("B", "Most natural", 1.0),
    ("C", "Strongest style adaptation", 1.35),
)

#: Operations that may not run in the conservative candidate: they change
#: shape rather than surface.
_STRUCTURAL = {
    "restructure_paragraphs", "drop_restated_sentences", "trim_summary_close",
    "merge_short_sentences", "rhythm_pass", "soften_imperatives",
}


@dataclass
class Candidate:
    label: str
    description: str
    text: str
    score: QualityScore
    changes: List[Dict[str, str]] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)
    rejected_reason: str = ""

    @property
    def accepted(self) -> bool:
        return self.score.accepted and not self.rejected_reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "description": self.description,
            "text": self.text,
            "accepted": self.accepted,
            "rejected_reason": self.rejected_reason,
            "scores": self.score.to_dict(),
            "operations": self.operations,
            "changes": self.changes,
        }


@dataclass
class HumanizeResult:
    original: str
    language: str
    locale: str
    options: Dict[str, Any]
    plan: Dict[str, Any]
    candidates: List[Candidate] = field(default_factory=list)
    recommended: str = ""
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def best(self) -> Optional[Candidate]:
        for c in self.candidates:
            if c.label == self.recommended:
                return c
        return next((c for c in self.candidates if c.accepted), None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "locale": self.locale,
            "options": self.options,
            "plan": self.plan,
            "candidates": [c.to_dict() for c in self.candidates],
            "recommended": self.recommended,
            "warnings": self.warnings,
            "notes": self.notes,
        }


class Humanizer:
    """Meaning-preserving naturalness rewriting for Dutch and English."""

    #: Stated in every result. The system is not built to defeat detection.
    DISCLAIMER = (
        "This rewrite is optimised for naturalness, clarity and your own voice — "
        "not for changing any detector's opinion, which nothing here targets."
    )

    def __init__(self, backend: Optional[Any] = None) -> None:
        # A model-backed rewriter can be plugged in here; the rule engine is
        # the default so the system works offline and deterministically.
        self.backend = backend

    def humanize(
        self,
        text: str,
        options: Optional[HumanizeOptions] = None,
        profile: Optional[StyleProfile] = None,
    ) -> HumanizeResult:
        text = (text or "").strip()
        options = options or HumanizeOptions()

        lang = Language.parse(options.language)
        if lang is Language.UNKNOWN:
            guess = detect_language(text)
            lang = guess.language if guess.language is not Language.UNKNOWN else Language.EN
        language = lang.value
        locale = (options.locale or Locale.parse(options.locale, lang).value)

        if profile is not None and profile.language in ("nl", "en"):
            options = _profile_defaults(options, profile)

        plan = build_plan(text, options, language)
        result = HumanizeResult(
            original=text,
            language=language,
            locale=locale,
            options=options.to_dict(),
            plan=plan.to_dict(),
            notes=[self.DISCLAIMER],
        )
        if not text:
            result.warnings.append("No text supplied.")
            return result
        if len(text.split()) < 10:
            result.warnings.append(
                "Very short input: there is little to work with, and rewriting "
                "may change more than it improves."
            )

        for label, description, intensity in CANDIDATE_SPECS[: options.candidates]:
            candidate = self._build_candidate(
                text, plan, options, profile, language, locale,
                label, description, intensity,
            )
            result.candidates.append(candidate)

        accepted = [c for c in result.candidates if c.accepted]
        if accepted:
            result.recommended = max(accepted, key=lambda c: c.score.overall).label
        else:
            result.warnings.append(
                "Every rewrite changed something factual and was rejected. "
                "The original is unchanged."
            )
        if plan.findings:
            result.notes.append("Found: " + "; ".join(plan.findings) + ".")
        return result

    # -- internals ---------------------------------------------------------
    def _build_candidate(
        self,
        text: str,
        plan: Plan,
        options: HumanizeOptions,
        profile: Optional[StyleProfile],
        language: str,
        locale: str,
        label: str,
        description: str,
        intensity: float,
    ) -> Candidate:
        ops = list(plan.ops)
        if label == "A":
            ops = [o for o in ops if o not in _STRUCTURAL]

        rewritten, ctx = self._run(text, ops, options, profile, language, locale,
                                   intensity, seed_offset=ord(label))
        score = score_rewrite(text, rewritten, options, language, profile)

        if not score.accepted:
            # One repair attempt: drop the operations that can lose content and
            # run again gently.  If it still fails, the original stands.
            safe_ops = [o for o in ops if o not in _STRUCTURAL and o != "drop_stock_phrases"]
            retry, retry_ctx = self._run(text, safe_ops, options, profile, language,
                                         locale, intensity * 0.5, seed_offset=ord(label) + 7)
            retry_score = score_rewrite(text, retry, options, language, profile)
            if retry_score.accepted:
                return Candidate(label, description + " (repaired)", retry, retry_score,
                                 [c.to_dict() for c in retry_ctx.changes],
                                 retry_ctx.used_ops())
            return Candidate(
                label, description, text, score,
                [c.to_dict() for c in ctx.changes], ctx.used_ops(),
                rejected_reason=score.meaning["violations"][0]["detail"]
                if score.meaning and score.meaning.get("violations") else "meaning changed",
            )

        return Candidate(label, description, rewritten, score,
                         [c.to_dict() for c in ctx.changes], ctx.used_ops())

    def _run(
        self,
        text: str,
        ops: Sequence[str],
        options: HumanizeOptions,
        profile: Optional[StyleProfile],
        language: str,
        locale: str,
        intensity: float,
        seed_offset: int,
    ):
        ctx = Context(
            options=options,
            language=language,
            locale=locale,
            rng=random.Random(options.seed + seed_offset),
            style=profile,
            intensity=intensity,
            original=text,
        )
        protected = ctx.protect(text)
        rewritten = run_ops(protected, ctx, [o for o in ops if o in OPS])
        rewritten = ctx.restore(rewritten)
        return rewritten, ctx


def _profile_defaults(options: HumanizeOptions, profile: StyleProfile) -> HumanizeOptions:
    """Let a style profile fill in controls the user did not set."""
    defaults = HumanizeOptions().to_dict()
    data = options.to_dict()
    if data["formality"] == defaults["formality"]:
        data["formality"] = profile.formality
    if data["contractions"] == defaults["contractions"]:
        data["contractions"] = (
            "conversational" if profile.contraction_rate > 2.0
            else "normal" if profile.contraction_rate > 0.8
            else "light" if profile.contraction_rate > 0.2
            else "none"
        )
    if data["directness"] == defaults["directness"]:
        data["directness"] = profile.directness
    if data["sentence_variation"] == defaults["sentence_variation"]:
        data["sentence_variation"] = max(0.2, min(1.0, profile.sentence_variation))
    if not data["locale"] and profile.locale:
        data["locale"] = profile.locale
    return HumanizeOptions(**data)
