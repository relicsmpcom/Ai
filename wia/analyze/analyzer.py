"""Writing & style analysis.

The third of the four systems in the roadmap.  Where the detector answers
"how was this likely made" and the humanizer answers "make it read better",
the analyzer answers "what is actually going on in this text" — in terms a
writer can act on without accepting a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import re

from wia.features import Doc, extract
from wia.features.lexicons import CORPORATE_FILLER, FORMAL_CONNECTIVES, get as lex_get
from wia.humanizer.critics import naturalness
from wia.humanizer.style_dna import StyleProfile, extract_style
from wia.lang import detect_language
from wia.text.segment import paragraphs, sentences
from wia.text.tokens import mean, stdev
from wia.types import Language


@dataclass
class Issue:
    kind: str
    severity: str  # info | minor | major
    message: str
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity,
                "message": self.message, "examples": self.examples}


@dataclass
class AnalysisReport:
    language: str = "en"
    words: int = 0
    sentences: int = 0
    paragraphs: int = 0
    reading_seconds: int = 0
    readability: Dict[str, Any] = field(default_factory=dict)
    rhythm: Dict[str, Any] = field(default_factory=dict)
    vocabulary: Dict[str, Any] = field(default_factory=dict)
    tone: Dict[str, Any] = field(default_factory=dict)
    structure: Dict[str, Any] = field(default_factory=dict)
    naturalness: Dict[str, Any] = field(default_factory=dict)
    issues: List[Issue] = field(default_factory=list)
    style: Dict[str, Any] = field(default_factory=dict)
    detection: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "words": self.words,
            "sentences": self.sentences,
            "paragraphs": self.paragraphs,
            "reading_seconds": self.reading_seconds,
            "readability": self.readability,
            "rhythm": self.rhythm,
            "vocabulary": self.vocabulary,
            "tone": self.tone,
            "structure": self.structure,
            "naturalness": self.naturalness,
            "issues": [i.to_dict() for i in self.issues],
            "style": self.style,
            "detection": self.detection,
        }


_READABILITY_LABELS = (
    (0.30, "hard going — long sentences and heavy words"),
    (0.50, "demanding but readable"),
    (0.70, "comfortable for most readers"),
    (1.01, "very easy — short sentences, plain words"),
)


def analyze(text: str, language: str = "auto", *, with_detection: bool = True) -> AnalysisReport:
    text = (text or "").strip()
    lang = Language.parse(language)
    if lang is Language.UNKNOWN:
        guess = detect_language(text)
        lang = guess.language if guess.language is not Language.UNKNOWN else Language.EN

    doc = Doc(text, lang.value)
    f = extract(doc)
    report = AnalysisReport(language=lang.value)
    if not text:
        return report

    segs = sentences(text)
    paras = paragraphs(text)
    lengths = doc.sentence_lengths
    report.words = doc.n_words
    report.sentences = len(segs)
    report.paragraphs = len(paras)
    report.reading_seconds = int(round(doc.n_words / 200 * 60))

    label = next(l for threshold, l in _READABILITY_LABELS if f["readability"] < threshold)
    report.readability = {
        "score": round(f["readability"] * 100, 1),
        "label": label,
        "syllables_per_word": round(f["syllables_per_word"], 2),
        "mean_sentence_length": round(f["mean_sentence_len"], 1),
    }
    report.rhythm = {
        "mean": round(mean(lengths), 1),
        "sd": round(stdev(lengths), 1),
        "variation": round(f["sentence_len_cv"], 3),
        "shortest": min(lengths) if lengths else 0,
        "longest": max(lengths) if lengths else 0,
        "short_share": round(f["short_sentence_ratio"], 3),
        "long_share": round(f["long_sentence_ratio"], 3),
        "lengths": lengths,
    }
    report.vocabulary = {
        "variety": round(f["mattr"], 3),
        "used_once": round(f["hapax_ratio"], 3),
        "mean_word_length": round(f["mean_word_len"], 2),
        "long_word_share": round(f["long_word_ratio"], 3),
        "top_words": _top_content_words(doc),
    }
    report.tone = {
        "formality": _formality(f),
        "hedges_per_100w": round(f["hedge_rate"], 2),
        "boosters_per_100w": round(f["booster_rate"], 2),
        "first_person_per_100w": round(f["first_person_rate"], 2),
        "second_person_per_100w": round(f["second_person_rate"], 2),
        "contractions_per_100w": round(f["contraction_rate"], 2),
        "questions_per_100w": round(f["question_rate"], 2),
    }
    report.structure = {
        "paragraph_words": [len(p.text.split()) for p in paras],
        "paragraph_variation": round(f["paragraph_len_cv"], 3),
        "opening_diversity": round(f["opening_diversity"], 3),
        "transitions_used": _transitions_used(doc, lang.value),
        "list_share": round(f["list_marker_ratio"], 3),
    }

    nat = naturalness(text, lang.value)
    report.naturalness = nat.to_dict()
    report.issues = _find_issues(doc, f, segs, paras, lang.value)

    profile: StyleProfile = extract_style([text], lang.value)
    report.style = {"profile": profile.to_dict(), "description": profile.describe()}

    if with_detection and doc.n_words >= 20:
        from wia.detector import Detector

        result = Detector.load().detect(text, language=lang.value)
        report.detection = result.to_dict()
    return report


def _formality(f: Dict[str, float]) -> Dict[str, Any]:
    score = 3.0
    score += 1.4 * min(1.0, max(0.0, (f["long_word_ratio"] - 0.15) / 0.12))
    score += 0.8 * min(1.0, f["formal_connective_rate"] / 1.5)
    score -= 1.2 * min(1.0, f["contraction_rate"] / 2.0)
    score -= 0.8 * min(1.0, f["exclamation_rate"] / 1.0)
    score -= 0.5 * min(1.0, f["first_person_rate"] / 3.0)
    level = int(max(1, min(6, round(score))))
    return {
        "level": level,
        "label": {1: "very casual", 2: "conversational", 3: "neutral",
                  4: "professional", 5: "formal", 6: "academic"}[level],
    }


def _top_content_words(doc: Doc, limit: int = 8) -> List[Dict[str, Any]]:
    fw = doc.function_words
    counts: Dict[str, int] = {}
    for w in doc.words:
        if w in fw or len(w) < 4:
            continue
        counts[w] = counts.get(w, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [{"word": w, "count": n} for w, n in ordered if n > 1]


def _transitions_used(doc: Doc, language: str) -> List[Dict[str, Any]]:
    from wia.features.lexicons import CASUAL_CONNECTIVES

    pool = lex_get(FORMAL_CONNECTIVES, language) | lex_get(CASUAL_CONNECTIVES, language)
    hay = doc.phrase_haystack
    used = [(p, hay.count(f" {p} ")) for p in pool]
    return [{"transition": p, "count": n}
            for p, n in sorted(used, key=lambda kv: -kv[1]) if n][:8]


def _find_issues(doc: Doc, f: Dict[str, float], segs, paras, language: str) -> List[Issue]:
    issues: List[Issue] = []

    long_sentences = [s.text for s in segs if len(s.text.split()) > 32]
    if long_sentences:
        issues.append(Issue(
            "long_sentences", "minor" if len(long_sentences) < 3 else "major",
            f"{len(long_sentences)} sentence(s) run past 32 words.",
            [s[:110] + "…" for s in long_sentences[:3]],
        ))

    if f["sentence_len_cv"] < 0.30 and len(segs) >= 5:
        issues.append(Issue(
            "flat_rhythm", "major",
            "Sentence lengths barely vary, which makes the text read flat.",
        ))

    openings: Dict[str, List[str]] = {}
    for s in segs:
        first = s.text.split()[:1]
        if first:
            openings.setdefault(first[0].lower().strip(",."), []).append(s.text[:60])
    repeated = {k: v for k, v in openings.items() if len(v) >= 3}
    if repeated:
        worst = max(repeated, key=lambda k: len(repeated[k]))
        issues.append(Issue(
            "repeated_openings", "minor",
            f"{len(repeated[worst])} sentences start with “{worst}”.",
            repeated[worst][:3],
        ))

    filler = lex_get(CORPORATE_FILLER, language)
    hits = sorted({w for w in doc.words if w in filler})
    if len(hits) >= 4 or f["corporate_filler_rate"] > 1.5:
        issues.append(Issue(
            "abstract_vocabulary", "minor",
            "A lot of abstract business vocabulary; concrete words land harder.",
            hits[:8],
        ))

    if f["template_phrase_rate"] > 0.8:
        issues.append(Issue(
            "stock_phrasing", "minor",
            "Several stock phrases that could be cut without losing anything.",
        ))

    if f["adjacent_sentence_overlap"] > 0.22:
        issues.append(Issue(
            "restatement", "minor",
            "Neighbouring sentences repeat each other's content.",
        ))

    sizes = [len(p.text.split()) for p in paras]
    if len(sizes) >= 3 and f["uniform_paragraph_size"] > 0.65:
        issues.append(Issue(
            "uniform_paragraphs", "minor",
            "Every paragraph is close to the same length.",
        ))
    if sizes and max(sizes) > 160:
        issues.append(Issue(
            "long_paragraph", "minor",
            f"The longest paragraph runs to {max(sizes)} words with no break.",
        ))

    if language == "nl":
        je = len(re.findall(r"\b(?:je|jij|jouw|jullie)\b", doc.lowered))
        u = len(re.findall(r"\b(?:u|uw)\b", doc.lowered))
        if je and u and min(je, u) / max(je, u) > 0.25:
            issues.append(Issue(
                "register_mix", "major",
                f"The text mixes “je” ({je}×) and “u” ({u}×). Pick one.",
            ))

    us = len(re.findall(r"\b\w+(?:ize|izes|ized|izing|ization)\b", doc.lowered))
    uk = len(re.findall(r"\b\w+(?:ise|ises|ised|ising|isation)\b", doc.lowered))
    if us and uk and min(us, uk) / max(us, uk) > 0.3 and language == "en":
        issues.append(Issue(
            "spelling_mix", "minor",
            f"US (-ize, {us}×) and UK (-ise, {uk}×) spellings are mixed.",
        ))

    if f["digit_rate"] < 0.2 and f["proper_noun_rate"] < 0.6 and doc.n_words > 120:
        issues.append(Issue(
            "no_specifics", "minor",
            "Almost no numbers or names. Concrete detail is what makes writing "
            "convincing — though never add detail you do not have.",
        ))
    return issues


def compare(left: str, right: str, language: str = "auto") -> Dict[str, Any]:
    """Side-by-side comparison for the Compare screen."""
    from wia.meaning.guard import check as meaning_check

    a = analyze(left, language, with_detection=True)
    b = analyze(right, a.language, with_detection=True)
    meaning = meaning_check(left, right, a.language)

    def delta(x: float, y: float) -> float:
        return round(y - x, 2)

    return {
        "left": a.to_dict(),
        "right": b.to_dict(),
        "meaning": meaning.to_dict(),
        "deltas": {
            "words": b.words - a.words,
            "naturalness": delta(a.naturalness["score"], b.naturalness["score"]),
            "readability": delta(a.readability["score"], b.readability["score"]),
            "sentence_variation": delta(a.rhythm["variation"], b.rhythm["variation"]),
            "mean_sentence_length": delta(a.rhythm["mean"], b.rhythm["mean"]),
            "formality": b.tone["formality"]["level"] - a.tone["formality"]["level"],
            "ai_probability": (
                delta(a.detection["ai_probability"], b.detection["ai_probability"])
                if a.detection and b.detection else None
            ),
        },
    }
