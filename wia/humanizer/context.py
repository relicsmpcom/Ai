"""Shared state for a rewrite pass, plus the protection mechanism.

Before any operation touches the text, the spans that must survive verbatim —
quotations, URLs, code, reference numbers, anything the caller listed in
``preserve`` — are replaced by opaque placeholders.  Operations cannot damage
what they cannot see.  The placeholders are restored at the end.

This is belt *and* braces: the meaning guard would catch such damage anyway,
but a rewrite that never breaks a quote in the first place beats one that gets
rejected and retried.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from wia.lexicons import load as load_lexicon
from wia.meaning.anchors import _CODEISH_RE, _ORDER_ID_RE, _QUOTE_RE, _URL_RE

_PLACEHOLDER = "\u0002{}\u0003"
_PLACEHOLDER_RE = re.compile("\\u0002(\\d+)\\u0003")


@dataclass
class Change:
    op: str
    before: str
    after: str
    reason: str = ""

    def to_dict(self) -> dict:
        return {"op": self.op, "before": self.before, "after": self.after,
                "reason": self.reason}


@dataclass
class Context:
    options: Any
    language: str = "en"
    locale: str = "en-INT"
    rng: random.Random = field(default_factory=lambda: random.Random(0))
    style: Optional[Any] = None
    changes: List[Change] = field(default_factory=list)
    intensity: float = 1.0  # candidate-level dial: A is gentler than C
    original: str = ""      # the untouched input, for repair decisions
    _protected: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.lex: Dict[str, Any] = load_lexicon(self.language)

    # -- change log --------------------------------------------------------
    def log(self, op: str, before: str, after: str, reason: str = "") -> None:
        if before != after:
            self.changes.append(Change(op, before, after, reason))

    def used_ops(self) -> List[str]:
        seen: List[str] = []
        for c in self.changes:
            if c.op not in seen:
                seen.append(c.op)
        return seen

    # -- protection --------------------------------------------------------
    def protect(self, text: str) -> str:
        """Mask spans that must survive the rewrite untouched."""
        self._protected = []

        def stash(match: re.Match) -> str:
            self._protected.append(match.group(0))
            return _PLACEHOLDER.format(len(self._protected) - 1)

        for phrase in sorted(getattr(self.options, "preserve", []) or [], key=len, reverse=True):
            text = re.sub(re.escape(phrase), stash, text)
        for pattern in (_URL_RE, _QUOTE_RE, _CODEISH_RE, _ORDER_ID_RE):
            text = pattern.sub(stash, text)
        return text

    def restore(self, text: str) -> str:
        def put(match: re.Match) -> str:
            idx = int(match.group(1))
            return self._protected[idx] if idx < len(self._protected) else match.group(0)

        return _PLACEHOLDER_RE.sub(put, text)

    @staticmethod
    def has_placeholder(text: str) -> bool:
        return bool(_PLACEHOLDER_RE.search(text))

    # -- helpers -----------------------------------------------------------
    @property
    def is_nl(self) -> bool:
        return self.language.startswith("nl")

    def chance(self, probability: float) -> bool:
        """Seeded coin flip, scaled by how aggressive this candidate is."""
        return self.rng.random() < probability * self.intensity
