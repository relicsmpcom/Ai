"""The meaning-preservation guard and factuality check.

A rewrite is compared against its source on the things a reader would call
"what it said": numbers, dates, names, references, quotations, whether a
sentence was negative, and how certain the writer was.  Any candidate that
moves one of those is rejected before it reaches the user — a humanizer that
quietly turns "grew approximately 18%" into "grew more than 20%" is worse than
useless, it is a liability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from wia.lang import function_words
from wia.meaning.anchors import Anchors, extract_anchors
from wia.text.segment import sentences
from wia.text.tokens import words

# How much each kind of drift costs, and whether it blocks the rewrite.
SEVERITY: Dict[str, Tuple[float, bool]] = {
    # kind: (penalty, blocking)
    "number_changed": (0.30, True),
    "number_dropped": (0.18, True),
    "number_added": (0.30, True),
    "date_changed": (0.25, True),
    "date_dropped": (0.15, True),
    "date_added": (0.25, True),
    "time_changed": (0.20, True),
    "entity_dropped": (0.10, False),
    "entity_added": (0.22, True),
    "citation_changed": (0.30, True),
    "url_changed": (0.30, True),
    "identifier_changed": (0.30, True),
    "technical_dropped": (0.12, False),
    "quote_altered": (0.35, True),
    "polarity_flipped": (0.40, True),
    "certainty_raised": (0.20, True),
    "certainty_lowered": (0.08, False),
    "content_dropped": (0.15, False),
    "length_collapsed": (0.12, False),
}


@dataclass
class Violation:
    kind: str
    detail: str
    original: str = ""
    rewrite: str = ""

    @property
    def penalty(self) -> float:
        return SEVERITY.get(self.kind, (0.1, False))[0]

    @property
    def blocking(self) -> bool:
        return SEVERITY.get(self.kind, (0.1, False))[1]

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "detail": self.detail,
            "original": self.original, "rewrite": self.rewrite,
            "penalty": self.penalty, "blocking": self.blocking,
        }


@dataclass
class MeaningReport:
    score: float = 1.0
    violations: List[Violation] = field(default_factory=list)
    content_coverage: float = 1.0
    certainty_shift: float = 0.0
    length_ratio: float = 1.0

    @property
    def passed(self) -> bool:
        return not any(v.blocking for v in self.violations)

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 4),
            "passed": self.passed,
            "content_coverage": round(self.content_coverage, 4),
            "certainty_shift": round(self.certainty_shift, 4),
            "length_ratio": round(self.length_ratio, 4),
            "violations": [v.to_dict() for v in self.violations],
        }

    def summary(self) -> str:
        if self.passed and not self.violations:
            return "Meaning preserved: no anchors moved."
        if self.passed:
            return (
                f"Meaning preserved ({self.score:.0%}) with "
                f"{len(self.violations)} minor difference(s)."
            )
        blocking = [v for v in self.violations if v.blocking]
        return f"Rewrite rejected: {blocking[0].detail}"


def _diff(a: Sequence[str], b: Sequence[str]) -> Tuple[List[str], List[str]]:
    sa, sb = set(a), set(b)
    return sorted(sa - sb), sorted(sb - sa)


def _mentions(text: str, token: str) -> bool:
    return bool(re.search(rf"(?<![\w'’]){re.escape(token)}(?![\w'’])", text, re.IGNORECASE))


def _norm_quote(q: str) -> str:
    return " ".join(q.lower().split())


def align_sentences(original: str, rewrite: str) -> List[Tuple[Optional[str], Optional[str]]]:
    """Greedy content-overlap alignment between two versions of a text.

    Used to compare polarity sentence by sentence: a rewrite may split, merge
    or reorder sentences, so a positional comparison would be meaningless.
    """
    src = [s.text for s in sentences(original)]
    dst = [s.text for s in sentences(rewrite)]
    src_sets = [set(words(s)) for s in src]
    dst_sets = [set(words(s)) for s in dst]
    used: set[int] = set()
    pairs: List[Tuple[Optional[str], Optional[str]]] = []
    for i, s_set in enumerate(src_sets):
        best, best_score = None, 0.0
        for j, d_set in enumerate(dst_sets):
            if j in used or not (s_set | d_set):
                continue
            score = len(s_set & d_set) / len(s_set | d_set)
            if score > best_score:
                best, best_score = j, score
        if best is not None and best_score >= 0.20:
            used.add(best)
            pairs.append((src[i], dst[best]))
        else:
            pairs.append((src[i], None))
    for j, d in enumerate(dst):
        if j not in used:
            pairs.append((None, d))
    return pairs


def check(original: str, rewrite: str, language: str = "en") -> MeaningReport:
    lang = "nl" if str(language).startswith("nl") else "en"
    a: Anchors = extract_anchors(original, lang)
    b: Anchors = extract_anchors(rewrite, lang)
    report = MeaningReport()
    V = report.violations

    # --- hard anchors -----------------------------------------------------
    for kind, left, right, label in (
        ("number", a.numbers, b.numbers, "number"),
        ("date", a.dates, b.dates, "date"),
        ("time", a.times, b.times, "time"),
    ):
        dropped, added = _diff(left, right)
        if dropped and added:
            V.append(Violation(f"{kind}_changed",
                               f"{label} changed: {', '.join(dropped)} → {', '.join(added)}",
                               ", ".join(dropped), ", ".join(added)))
        elif dropped:
            V.append(Violation(f"{kind}_dropped",
                               f"{label} missing from the rewrite: {', '.join(dropped)}",
                               ", ".join(dropped)))
        elif added:
            V.append(Violation(f"{kind}_added",
                               f"{label} that is not in the original: {', '.join(added)}",
                               "", ", ".join(added)))

    dropped, added = _diff(a.entities, b.entities)
    # Sentence boundaries move during a rewrite, and a word that was
    # sentence-initial in one version can be mid-sentence in the other. Only
    # count a name as introduced if it does not occur in the source at all —
    # that is the question worth asking: did the rewrite invent someone?
    added = [e for e in added if not _mentions(original, e)]
    dropped = [e for e in dropped if not _mentions(rewrite, e)]
    if dropped:
        V.append(Violation("entity_dropped",
                           f"name(s) no longer mentioned: {', '.join(dropped[:6])}",
                           ", ".join(dropped[:6])))
    if added:
        V.append(Violation("entity_added",
                           f"name(s) introduced by the rewrite: {', '.join(added[:6])}",
                           "", ", ".join(added[:6])))

    for kind, left, right in (
        ("citation", a.citations, b.citations),
        ("url", a.urls, b.urls),
        ("identifier", a.identifiers, b.identifiers),
    ):
        if set(left) != set(right):
            V.append(Violation(f"{kind}_changed",
                               f"{kind} changed: {sorted(set(left))} → {sorted(set(right))}"))

    dropped_tech, _ = _diff(a.technical, b.technical)
    if dropped_tech:
        V.append(Violation("technical_dropped",
                           f"technical term(s) removed: {', '.join(dropped_tech[:5])}"))

    src_quotes = {_norm_quote(q) for q in a.quotes}
    dst_quotes = {_norm_quote(q) for q in b.quotes}
    if src_quotes - dst_quotes:
        V.append(Violation("quote_altered",
                           "a quotation was altered or removed; quoted words must "
                           "survive a rewrite untouched",
                           sorted(src_quotes - dst_quotes)[0][:120]))

    # --- polarity ---------------------------------------------------------
    # Two checks in series.  The document-level one asks whether any negation
    # cue actually appeared or disappeared; the sentence-level one localises
    # it.  Requiring both stops a sentence split from looking like a flipped
    # claim just because the alignment moved.
    from collections import Counter

    from wia.meaning.anchors import NEGATIONS

    negs = NEGATIONS[lang]
    src_cues = Counter(w for w in words(original) if w in negs)
    dst_cues = Counter(w for w in words(rewrite) if w in negs)
    if src_cues != dst_cues:
        for src, dst in align_sentences(original, rewrite):
            if not src or not dst:
                continue
            s_neg = any(w in negs for w in words(src))
            d_neg = any(w in negs for w in words(dst))
            if s_neg != d_neg:
                V.append(Violation(
                    "polarity_flipped",
                    "a sentence changed between positive and negative",
                    src[:120], dst[:120],
                ))
                break

    # --- certainty --------------------------------------------------------
    report.certainty_shift = b.certainty - a.certainty
    if report.certainty_shift > 0.12:
        V.append(Violation("certainty_raised",
                           f"the rewrite sounds more certain than the original "
                           f"({a.certainty:.2f} → {b.certainty:.2f})"))
    elif report.certainty_shift < -0.18:
        V.append(Violation("certainty_lowered",
                           f"the rewrite hedges more than the original "
                           f"({a.certainty:.2f} → {b.certainty:.2f})"))

    # --- content coverage -------------------------------------------------
    fw = function_words(lang)
    src_content = {w for w in words(original) if w not in fw and len(w) > 3}
    dst_content = {w for w in words(rewrite) if w not in fw and len(w) > 3}
    if src_content:
        # Words may legitimately be replaced by synonyms; only a large loss of
        # distinct content is evidence that something was dropped.
        report.content_coverage = len(src_content & dst_content) / len(src_content)
        if report.content_coverage < 0.55:
            V.append(Violation(
                "content_dropped",
                f"only {report.content_coverage:.0%} of the original content words "
                "survive; check that nothing was cut",
            ))

    ow, rw = len(words(original)), len(words(rewrite))
    report.length_ratio = rw / ow if ow else 1.0
    if report.length_ratio < 0.6:
        V.append(Violation("length_collapsed",
                           f"the rewrite is {1 - report.length_ratio:.0%} shorter than "
                           "the original; detail may have been lost"))

    penalty = sum(v.penalty for v in V)
    report.score = max(0.0, 1.0 - penalty)
    return report
