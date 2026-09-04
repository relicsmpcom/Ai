"""HumanBench-NL/EN — schema, loading and slicing.

The roadmap is right that the benchmark comes first, and it is right that
"human vs AI" is the wrong label space.  Real text sits on a spectrum: a
person who ran their own paragraph through a spell checker has not co-written
it with a machine, and a generated draft someone rewrote for an hour is not
"AI text" in any sense a reader would recognise.

So samples carry a ten-point :class:`Provenance` label, and the three coarse
classes the product reports are *derived* from it.  Where you draw that
mapping is a product decision, and it lives in one visible place
(:data:`COARSE_MAP`) rather than being smeared across the training code.
"""

from __future__ import annotations

import enum
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "humanbench"


class Provenance(str, enum.Enum):
    FULLY_HUMAN = "fully_human"
    HUMAN_SPELLCHECK = "human_spellcheck"
    HUMAN_GRAMMAR_CORRECTION = "human_grammar_correction"
    HUMAN_AI_SUGGESTIONS = "human_ai_suggestions"
    HUMAN_HEAVILY_AI_EDITED = "human_heavily_ai_edited"
    MIXED = "mixed"
    AI_LIGHT_HUMAN_EDIT = "ai_light_human_edit"
    AI_HEAVY_HUMAN_EDIT = "ai_heavy_human_edit"
    FULLY_AI = "fully_ai"
    UNCERTAIN = "uncertain"


#: How the ten labelling classes collapse into the three reported classes.
#: Spelling and grammar correction stay firmly *human* — treating a spell
#: checker as co-authorship is how a detector ends up accusing dyslexic
#: writers.  A generated draft that a person rewrote heavily counts as mixed,
#: because a reader would recognise the person in it.
COARSE_MAP: Dict[Provenance, Optional[str]] = {
    Provenance.FULLY_HUMAN: "human",
    Provenance.HUMAN_SPELLCHECK: "human",
    Provenance.HUMAN_GRAMMAR_CORRECTION: "human",
    Provenance.HUMAN_AI_SUGGESTIONS: "mixed",
    Provenance.HUMAN_HEAVILY_AI_EDITED: "mixed",
    Provenance.MIXED: "mixed",
    Provenance.AI_HEAVY_HUMAN_EDIT: "mixed",
    Provenance.AI_LIGHT_HUMAN_EDIT: "ai",
    Provenance.FULLY_AI: "ai",
    Provenance.UNCERTAIN: None,  # reported, never trained on
}

LENGTH_BUCKETS: Sequence[tuple[str, int, int]] = (
    ("20-50", 20, 50),
    ("50-100", 50, 100),
    ("100-250", 100, 250),
    ("250-500", 250, 500),
    ("500-1000", 500, 1000),
    ("1000+", 1000, 10 ** 9),
)

DOMAINS = (
    "school_essay", "university", "business_email", "customer_support",
    "report", "blog", "journalism", "marketing", "product_description",
    "social", "chat", "technical_docs", "creative",
)


def length_bucket(n_words: int) -> str:
    for name, lo, hi in LENGTH_BUCKETS:
        if lo <= n_words < hi:
            return name
    return "20-50" if n_words < 20 else "1000+"


@dataclass
class Sample:
    id: str
    text: str
    language: str
    provenance: str
    domain: str = "general"
    locale: str = ""
    register: str = "neutral"
    source: str = "unknown"
    generator: str = ""
    split: str = "train"
    notes: str = ""
    tags: List[str] = field(default_factory=list)

    @property
    def n_words(self) -> int:
        return len(self.text.split())

    @property
    def bucket(self) -> str:
        return length_bucket(self.n_words)

    @property
    def coarse(self) -> Optional[str]:
        return COARSE_MAP.get(Provenance(self.provenance))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Sample":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


class Dataset:
    def __init__(self, samples: Sequence[Sample]):
        self.samples: List[Sample] = list(samples)

    def __len__(self) -> int:
        return len(self.samples)

    def __iter__(self) -> Iterator[Sample]:
        return iter(self.samples)

    # -- io ----------------------------------------------------------------
    @classmethod
    def load(cls, paths: Optional[Iterable[Path | str]] = None) -> "Dataset":
        files = (
            [Path(p) for p in paths]
            if paths
            else sorted(DATA_DIR.glob("*.jsonl"))
        )
        samples: List[Sample] = []
        for f in files:
            if not Path(f).exists():
                continue
            for line_no, line in enumerate(Path(f).read_text(encoding="utf-8").splitlines(), 1):
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                try:
                    samples.append(Sample.from_dict(json.loads(line)))
                except Exception as exc:  # pragma: no cover - corrupt data
                    raise ValueError(f"{f}:{line_no}: {exc}") from exc
        return cls(samples)

    def save(self, path: Path | str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            for s in self.samples:
                fh.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")

    # -- slicing -----------------------------------------------------------
    def filter(self, **kw) -> "Dataset":
        def ok(s: Sample) -> bool:
            return all(getattr(s, k, None) == v for k, v in kw.items())

        return Dataset([s for s in self.samples if ok(s)])

    def trainable(self) -> "Dataset":
        return Dataset([s for s in self.samples if s.coarse is not None])

    def split_by(self, split: str) -> "Dataset":
        return Dataset([s for s in self.samples if s.split == split])

    def slices(self) -> Dict[str, Dict[str, List[Sample]]]:
        """Group samples by the axes the report breaks results down on."""
        out: Dict[str, Dict[str, List[Sample]]] = {
            "language": {}, "domain": {}, "length": {}, "provenance": {}, "register": {},
        }
        for s in self.samples:
            out["language"].setdefault(s.language, []).append(s)
            out["domain"].setdefault(s.domain, []).append(s)
            out["length"].setdefault(s.bucket, []).append(s)
            out["provenance"].setdefault(s.provenance, []).append(s)
            out["register"].setdefault(s.register, []).append(s)
        return out

    def summary(self) -> Dict[str, object]:
        by_coarse: Dict[str, int] = {}
        for s in self.samples:
            by_coarse[str(s.coarse)] = by_coarse.get(str(s.coarse), 0) + 1
        sl = self.slices()
        return {
            "samples": len(self.samples),
            "words": sum(s.n_words for s in self.samples),
            "coarse": by_coarse,
            "language": {k: len(v) for k, v in sorted(sl["language"].items())},
            "provenance": {k: len(v) for k, v in sorted(sl["provenance"].items())},
            "domain": {k: len(v) for k, v in sorted(sl["domain"].items())},
            "length": {k: len(v) for k, v in sorted(sl["length"].items())},
            "splits": {
                sp: len([s for s in self.samples if s.split == sp])
                for sp in sorted({s.split for s in self.samples})
            },
        }


def validate(samples: Sequence[Sample]) -> List[str]:
    """Schema checks that run in CI so the corpus cannot rot silently."""
    problems: List[str] = []
    seen = set()
    for s in samples:
        if s.id in seen:
            problems.append(f"duplicate id: {s.id}")
        seen.add(s.id)
        if s.language not in ("nl", "en"):
            problems.append(f"{s.id}: unsupported language {s.language!r}")
        try:
            Provenance(s.provenance)
        except ValueError:
            problems.append(f"{s.id}: unknown provenance {s.provenance!r}")
        if s.domain not in DOMAINS and s.domain != "general":
            problems.append(f"{s.id}: unknown domain {s.domain!r}")
        if s.n_words < 15:
            problems.append(f"{s.id}: too short ({s.n_words} words)")
        if s.split not in ("train", "dev", "test"):
            problems.append(f"{s.id}: unknown split {s.split!r}")
        if not s.source:
            problems.append(f"{s.id}: missing source provenance")
    return problems
