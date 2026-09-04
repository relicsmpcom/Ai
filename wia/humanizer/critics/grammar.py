"""Surface grammar and typography checks.

Not a grammar checker — a *damage* checker.  Its job is to notice when a
rewrite operation left the text broken: a dangling comma, a lower-case
sentence start, an unbalanced bracket, a doubled word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

from wia.text.segment import sentences

_CHECKS: Tuple[Tuple[str, str, float], ...] = (
    (r"\s+[,.;:!?]", "space before punctuation", 3.0),
    (r"[,;:][^\s\d\"'”’)\]]", "missing space after punctuation", 3.0),
    (r"\b(\w+)\s+\1\b", "doubled word", 5.0),
    (r"[ \t]{2,}\S", "double space", 1.5),
    (r",\s*[.!?]", "comma before a full stop", 4.0),
    (r"\(\s*\)", "empty parentheses", 4.0),
    (r"\s,", "floating comma", 3.0),
    (r"[.!?]{4,}", "run of punctuation", 2.0),
    (r"\b(?:a)\s+[aeiou]\w+", "article agreement (a/an)", 2.5),
    (r"^\s*[,.;:]", "line starts with punctuation", 4.0),
)


@dataclass
class GrammarReport:
    score: float = 100.0
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"score": round(self.score, 1), "issues": self.issues}


def grammar_delta(original: str, rewrite: str, language: str = "en") -> GrammarReport:
    """Score only the damage the *rewrite* introduced.

    Penalising a rewrite for lower-case sentence starts that the author wrote
    on purpose would push the humanizer to overwrite people's voices, which is
    the opposite of the job.
    """
    before = grammar_check(original, language)
    after = grammar_check(rewrite, language)
    baseline = {i.split(" (")[0] for i in before.issues}
    report = GrammarReport()
    report.issues = [i for i in after.issues if i.split(" (")[0] not in baseline]
    # Start from the rewrite's own score, then hand back the penalties that
    # were already there in the original.
    report.score = min(100.0, after.score + (100.0 - before.score))
    return report


def grammar_check(text: str, language: str = "en") -> GrammarReport:
    report = GrammarReport()
    penalty = 0.0

    for pattern, label, weight in _CHECKS:
        hits = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
        if hits:
            penalty += weight * min(3, len(hits))
            report.issues.append(f"{label} ({len(hits)}×)")

    for opener, closer, label in (("(", ")", "parentheses"), ("[", "]", "brackets")):
        if text.count(opener) != text.count(closer):
            penalty += 4.0
            report.issues.append(f"unbalanced {label}")
    for mark, label in (('"', "double quotes"), ("“", "smart quotes")):
        if mark == '"' and text.count('"') % 2:
            penalty += 3.0
            report.issues.append(f"unbalanced {label}")
    if text.count("“") != text.count("”"):
        penalty += 3.0
        report.issues.append("unbalanced smart quotes")

    lowercase_starts = sum(
        1 for s in sentences(text)
        if s.text[:1].islower() and not s.text.startswith(("'", "iPhone", "eBay"))
    )
    if lowercase_starts:
        penalty += 1.5 * min(4, lowercase_starts)
        report.issues.append(f"sentence starts lower-case ({lowercase_starts}×)")

    stripped = text.rstrip()
    if stripped and stripped[-1] not in ".!?:\"'”’)]…":
        penalty += 2.0
        report.issues.append("text does not end with punctuation")

    report.score = max(0.0, 100.0 - penalty)
    return report
