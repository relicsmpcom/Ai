"""Shared value types.

Everything the platform passes between subsystems lives here so that the
detector, the humanizer and the benchmark harness agree on vocabulary.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


class Language(str, enum.Enum):
    NL = "nl"
    EN = "en"
    UNKNOWN = "unknown"

    @classmethod
    def parse(cls, value: str | None) -> "Language":
        if not value:
            return cls.UNKNOWN
        v = value.strip().lower()
        if v in ("nl", "dut", "nld", "dutch", "nederlands"):
            return cls.NL
        if v in ("en", "eng", "english", "engels"):
            return cls.EN
        return cls.UNKNOWN


class Locale(str, enum.Enum):
    NL_NL = "nl-NL"
    NL_BE = "nl-BE"
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_INT = "en-INT"

    @classmethod
    def parse(cls, value: str | None, language: Language | None = None) -> "Locale":
        table = {
            "nl": cls.NL_NL,
            "nl-nl": cls.NL_NL,
            "netherlands": cls.NL_NL,
            "nl-be": cls.NL_BE,
            "be": cls.NL_BE,
            "flanders": cls.NL_BE,
            "vlaams": cls.NL_BE,
            "us": cls.EN_US,
            "en-us": cls.EN_US,
            "uk": cls.EN_GB,
            "gb": cls.EN_GB,
            "en-gb": cls.EN_GB,
            "int": cls.EN_INT,
            "en-int": cls.EN_INT,
            "international": cls.EN_INT,
        }
        if value:
            hit = table.get(value.strip().lower())
            if hit:
                return hit
        if language is Language.NL:
            return cls.NL_NL
        return cls.EN_INT

    @property
    def language(self) -> Language:
        return Language.NL if self.value.startswith("nl") else Language.EN


class AuthorshipClass(str, enum.Enum):
    """Coarse output classes (section 4 of the roadmap).

    The fine-grained 10-point provenance spectrum used for *labelling* lives in
    :class:`wia.bench.dataset.Provenance`; these are the classes the product
    actually reports, because they are the only ones a detector can carry
    calibrated evidence for.
    """

    LIKELY_HUMAN = "likely_human"
    MOSTLY_HUMAN = "mostly_human"
    MIXED = "mixed"
    MOSTLY_AI = "mostly_ai"
    LIKELY_AI = "likely_ai"
    UNCERTAIN = "uncertain"

    @property
    def label(self) -> str:
        return {
            "likely_human": "Likely human",
            "mostly_human": "Mostly human",
            "mixed": "Mixed / AI-assisted",
            "mostly_ai": "Mostly AI",
            "likely_ai": "Likely AI",
            "uncertain": "Uncertain",
        }[self.value]


class Confidence(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class Segment:
    """A slice of the input text, with offsets back into the original."""

    index: int
    text: str
    start: int
    end: int
    kind: str = "sentence"  # sentence | paragraph | window

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class SegmentResult:
    segment: Segment
    human_probability: float
    mixed_probability: float
    ai_probability: float
    label: AuthorshipClass
    confidence: Confidence
    # Segment scores are noisy by construction: short spans carry little
    # evidence.  ``reliability`` says how much weight the UI should give this.
    reliability: float = 0.0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["segment"] = asdict(self.segment)
        d["label"] = self.label.value
        d["confidence"] = self.confidence.value
        return d


@dataclass
class DetectionResult:
    language: Language
    language_confidence: float
    human_probability: float
    mixed_probability: float
    ai_probability: float
    label: AuthorshipClass
    confidence: Confidence
    words: int
    segments: List[SegmentResult] = field(default_factory=list)
    mixed_authorship: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, float] = field(default_factory=dict)
    explanations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    domain: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language.value,
            "language_confidence": round(self.language_confidence, 4),
            "human_probability": round(self.human_probability, 4),
            "mixed_probability": round(self.mixed_probability, 4),
            "ai_probability": round(self.ai_probability, 4),
            "label": self.label.value,
            "label_text": self.label.label,
            "confidence": self.confidence.value,
            "words": self.words,
            "domain": self.domain,
            "segments": [s.to_dict() for s in self.segments],
            "mixed_authorship": self.mixed_authorship,
            "features": {k: round(v, 5) for k, v in self.features.items()},
            "explanations": self.explanations,
            "warnings": self.warnings,
        }
