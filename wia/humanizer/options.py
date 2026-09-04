"""Every control the humanizer exposes, in one place.

The roadmap lists a lot of knobs.  They are all here, they all have sane
defaults, and none of them is allowed to change what the text *says* — that is
the meaning guard's job, and it runs after every one of them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

TONES = (
    "casual", "friendly", "professional", "formal", "academic", "confident",
    "warm", "concise", "persuasive", "neutral", "enthusiastic", "serious",
    "technical", "humorous", "empathetic",
)
DIRECTNESS = ("very_direct", "direct", "balanced", "diplomatic", "soft")
CONCISENESS = ("shorten", "concise", "balanced", "detailed", "expanded")
COMPLEXITY = ("a2", "b1", "b2", "c1", "academic")
VOCABULARY = ("simple", "natural", "professional", "advanced", "academic", "casual")
CONTRACTIONS = ("none", "light", "normal", "conversational")
AUDIENCES = (
    "customer", "colleague", "manager", "student", "professor", "executive",
    "general", "technical", "teen", "social",
)
PURPOSES = (
    "explain", "persuade", "inform", "summarize", "sell", "request",
    "apologize", "complain", "teach", "entertain", "report",
)
EMOTIONS = ("neutral", "warm", "excited", "calm", "assertive", "empathetic", "urgent")
IDIOMS = ("none", "light", "normal")

#: Formality is a 1–6 scale; every op that cares reads it from here.
FORMALITY_LABELS = {
    1: "very casual", 2: "conversational", 3: "neutral",
    4: "professional", 5: "formal", 6: "academic",
}


def _clamp_choice(value: str, allowed, default: str) -> str:
    v = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return v if v in allowed else default


@dataclass
class HumanizeOptions:
    language: str = "auto"
    locale: str = ""
    mode: str = ""
    tone: str = "neutral"
    formality: int = 3
    directness: str = "balanced"
    conciseness: str = "balanced"
    complexity: str = "b2"
    vocabulary: str = "natural"
    contractions: str = "normal"
    idioms: str = "light"
    audience: str = "general"
    purpose: str = "inform"
    emotion: str = "neutral"
    sentence_variation: float = 0.6
    personal_voice: bool = True
    paragraph_restructuring: bool = True
    preserve: List[str] = field(default_factory=list)
    style_profile_id: str = ""
    seed: int = 0
    candidates: int = 3

    def __post_init__(self) -> None:
        self.tone = _clamp_choice(self.tone, TONES, "neutral")
        self.directness = _clamp_choice(self.directness, DIRECTNESS, "balanced")
        self.conciseness = _clamp_choice(self.conciseness, CONCISENESS, "balanced")
        self.complexity = _clamp_choice(self.complexity, COMPLEXITY, "b2")
        self.vocabulary = _clamp_choice(self.vocabulary, VOCABULARY, "natural")
        self.contractions = _clamp_choice(self.contractions, CONTRACTIONS, "normal")
        self.idioms = _clamp_choice(self.idioms, IDIOMS, "light")
        self.audience = _clamp_choice(self.audience, AUDIENCES, "general")
        self.purpose = _clamp_choice(self.purpose, PURPOSES, "inform")
        self.emotion = _clamp_choice(self.emotion, EMOTIONS, "neutral")
        try:
            self.formality = max(1, min(6, int(self.formality)))
        except (TypeError, ValueError):
            self.formality = 3
        try:
            self.sentence_variation = max(0.0, min(1.0, float(self.sentence_variation)))
        except (TypeError, ValueError):
            self.sentence_variation = 0.6
        self.candidates = max(1, min(5, int(self.candidates or 3)))
        self.preserve = [p for p in (self.preserve or []) if p and p.strip()]

    # -- convenience -------------------------------------------------------
    @property
    def formality_label(self) -> str:
        return FORMALITY_LABELS[self.formality]

    @property
    def wants_informal(self) -> bool:
        return self.formality <= 2 or self.tone in ("casual", "friendly", "humorous")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "HumanizeOptions":
        d = dict(d or {})
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        opts = cls(**known)
        if opts.mode:
            from wia.humanizer.modes import apply_mode

            opts = apply_mode(opts, opts.mode)
        return opts

    def merged(self, **overrides) -> "HumanizeOptions":
        data = self.to_dict()
        data.update({k: v for k, v in overrides.items() if v is not None})
        return HumanizeOptions(**data)
