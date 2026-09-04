"""Style DNA — a measurable fingerprint of how one person writes.

Everything in a profile is a *measurement of the user's own samples*.  Nothing
is inferred about them, nothing is stored that they did not paste in, and the
profile is small enough to show them in full — which is the only honest way to
offer "sound like me".
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from wia.features import Doc, extract
from wia.features.lexicons import BOOSTERS, FIRST_PERSON, HEDGES, get as lex_get
from wia.lang import detect_language, function_words
from wia.text.segment import paragraphs, sentences
from wia.text.tokens import mean, stdev, words


@dataclass
class StyleProfile:
    id: str = ""
    language: str = "en"
    locale: str = ""
    n_samples: int = 0
    n_words: int = 0

    mean_sentence_length: float = 17.0
    sentence_length_sd: float = 7.0
    sentence_variation: float = 0.45
    short_sentence_ratio: float = 0.18
    mean_paragraph_words: float = 60.0

    mean_word_length: float = 4.7
    long_word_ratio: float = 0.16
    vocabulary_richness: float = 0.72

    formality: int = 3
    directness: str = "balanced"
    contraction_rate: float = 1.0
    hedge_rate: float = 0.5
    booster_rate: float = 0.5
    first_person_rate: float = 1.5

    punctuation: Dict[str, float] = field(default_factory=dict)
    emoji_rate: float = 0.0

    favourite_openings: List[str] = field(default_factory=list)
    favourite_closings: List[str] = field(default_factory=list)
    favourite_transitions: List[str] = field(default_factory=list)
    favourite_expressions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "StyleProfile":
        d = dict(d or {})
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def describe(self) -> List[str]:
        """A profile the user can read and correct — not a black box."""
        out = [
            f"Sentences average {self.mean_sentence_length:.0f} words "
            f"(variation {self.sentence_variation:.2f}).",
            f"Paragraphs average {self.mean_paragraph_words:.0f} words.",
            f"Formality reads as {self.formality}/6.",
        ]
        if self.contraction_rate > 1.2:
            out.append("You contract freely.")
        elif self.contraction_rate < 0.3:
            out.append("You rarely use contracted forms.")
        if self.first_person_rate > 2.0:
            out.append("You write in the first person a lot.")
        if self.hedge_rate > 1.0:
            out.append("You hedge rather than assert.")
        if self.emoji_rate > 0.2:
            out.append("You use emoji.")
        for name, label in (("em_dash", "dashes"), ("semicolon", "semicolons"),
                            ("ellipsis", "ellipses"), ("exclamation", "exclamation marks")):
            if self.punctuation.get(name, 0) > 0.4:
                out.append(f"You use {label} more than most writers.")
        if self.favourite_openings:
            out.append("Typical openings: " + ", ".join(self.favourite_openings[:3]) + ".")
        if self.favourite_expressions:
            out.append("Recurring phrases: " + ", ".join(self.favourite_expressions[:4]) + ".")
        return out


_FORMAL_MARKERS = re.compile(
    r"\b(geachte|hierbij|derhalve|middels|conform|dient|yours sincerely|"
    r"further to|pursuant|kindly|hereby)\b", re.IGNORECASE)
_CASUAL_MARKERS = re.compile(
    r"\b(hoi|hey|yo|lol|haha|btw|gewoon|effe|ff|nou|man|dude|ok|okay|yeah|joh)\b|"
    r"[!]{2,}|\.\.\.", re.IGNORECASE)


def extract_style(samples: Sequence[str], language: str = "auto",
                  locale: str = "", profile_id: str = "") -> StyleProfile:
    """Build a profile from the writer's own samples."""
    texts = [s for s in samples if s and s.strip()]
    if not texts:
        return StyleProfile(id=profile_id or "empty")
    joined = "\n\n".join(texts)
    lang = language if language in ("nl", "en") else detect_language(joined).language.value
    if lang not in ("nl", "en"):
        lang = "en"

    doc = Doc(joined, lang)
    f = extract(doc)
    profile = StyleProfile(
        id=profile_id or hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16],
        language=lang,
        locale=locale,
        n_samples=len(texts),
        n_words=doc.n_words,
        mean_sentence_length=f["mean_sentence_len"],
        sentence_length_sd=stdev(doc.sentence_lengths),
        sentence_variation=f["sentence_len_cv"],
        short_sentence_ratio=f["short_sentence_ratio"],
        mean_paragraph_words=mean([len(p.text.split()) for p in paragraphs(joined)], 60.0),
        mean_word_length=f["mean_word_len"],
        long_word_ratio=f["long_word_ratio"],
        vocabulary_richness=f["mattr"],
        contraction_rate=f["contraction_rate"],
        hedge_rate=f["hedge_rate"],
        booster_rate=f["booster_rate"],
        first_person_rate=f["first_person_rate"],
        emoji_rate=f["emoji_rate"],
        punctuation={
            "comma": f["commas_per_sentence"],
            "em_dash": f["em_dash_rate"],
            "semicolon": f["semicolon_rate"],
            "colon": f["colon_rate"],
            "exclamation": f["exclamation_rate"],
            "question": f["question_rate"],
            "ellipsis": f["ellipsis_rate"],
            "parenthetical": f["parenthetical_rate"],
        },
    )

    formal_hits = len(_FORMAL_MARKERS.findall(joined))
    casual_hits = len(_CASUAL_MARKERS.findall(joined))
    score = 3.0
    score += 1.2 * min(1.0, formal_hits / 3.0)
    score -= 1.4 * min(1.0, casual_hits / 3.0)
    score += 0.8 * min(1.0, max(0.0, (f["long_word_ratio"] - 0.16) / 0.10))
    score -= 0.7 * min(1.0, f["contraction_rate"] / 2.0)
    profile.formality = int(max(1, min(6, round(score))))

    if f["hedge_rate"] > 1.2:
        profile.directness = "diplomatic"
    elif f["mean_sentence_len"] < 14 and f["hedge_rate"] < 0.4:
        profile.directness = "direct"

    profile.favourite_openings = _frequent_openings(joined)
    profile.favourite_closings = _frequent_closings(texts)
    profile.favourite_transitions = _frequent_transitions(doc, lang)
    profile.favourite_expressions = _favourite_expressions(doc, lang)
    return profile


def _frequent_openings(text: str, limit: int = 5) -> List[str]:
    firsts = []
    for seg in sentences(text):
        w = seg.text.split()
        if w:
            firsts.append(" ".join(w[:2]).strip(",.:;").lower())
    return [w for w, n in Counter(firsts).most_common(limit) if n > 1]


def _frequent_closings(texts: Sequence[str], limit: int = 3) -> List[str]:
    closings = []
    for t in texts:
        lines = [l.strip() for l in t.strip().split("\n") if l.strip()]
        if lines:
            closings.append(lines[-1][:60].lower())
    return [c for c, n in Counter(closings).most_common(limit) if n > 1]


def _frequent_transitions(doc: Doc, lang: str, limit: int = 5) -> List[str]:
    from wia.features.lexicons import CASUAL_CONNECTIVES, FORMAL_CONNECTIVES

    pool = lex_get(FORMAL_CONNECTIVES, lang) | lex_get(CASUAL_CONNECTIVES, lang)
    hay = " " + doc.lowered + " "
    counts = {p: hay.count(f" {p} ") for p in pool}
    return [p for p, n in sorted(counts.items(), key=lambda kv: -kv[1])[:limit] if n]


def _favourite_expressions(doc: Doc, lang: str, limit: int = 6) -> List[str]:
    fw = function_words(lang)
    grams = Counter(doc.trigrams) + Counter(doc.bigrams)
    out: List[str] = []
    for gram, count in grams.most_common(80):
        if count < 2:
            break
        toks = gram.split()
        if all(t in fw for t in toks) or any(t.isdigit() for t in toks):
            continue
        if any(gram in existing for existing in out):
            continue
        out.append(gram)
        if len(out) >= limit:
            break
    return out


def style_match(text: str, profile: StyleProfile) -> float:
    """0–100: how closely a text matches a profile on measurable habits."""
    doc = Doc(text, profile.language)
    f = extract(doc)
    checks = [
        (_closeness(f["mean_sentence_len"], profile.mean_sentence_length, 8.0), 1.5),
        (_closeness(f["sentence_len_cv"], profile.sentence_variation, 0.25), 1.0),
        (_closeness(f["mean_word_len"], profile.mean_word_length, 0.8), 1.0),
        (_closeness(f["contraction_rate"], profile.contraction_rate, 1.2), 1.0),
        (_closeness(f["first_person_rate"], profile.first_person_rate, 1.6), 1.0),
        (_closeness(f["hedge_rate"], profile.hedge_rate, 0.9), 0.8),
        (_closeness(f["exclamation_rate"], profile.punctuation.get("exclamation", 0.2), 0.6), 0.5),
        (_closeness(f["em_dash_rate"], profile.punctuation.get("em_dash", 0.2), 0.5), 0.5),
        (_closeness(f["commas_per_sentence"], profile.punctuation.get("comma", 1.1), 0.8), 0.7),
        (_closeness(f["emoji_rate"], profile.emoji_rate, 0.5), 0.4),
        (_closeness(
            mean([len(p.text.split()) for p in paragraphs(text)], 60.0),
            profile.mean_paragraph_words, 45.0), 0.6),
    ]
    total_weight = sum(w for _, w in checks)
    return 100.0 * sum(v * w for v, w in checks) / total_weight


def _closeness(value: float, target: float, tolerance: float) -> float:
    if tolerance <= 0:
        return 1.0
    return max(0.0, 1.0 - abs(value - target) / tolerance)
