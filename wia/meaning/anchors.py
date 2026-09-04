"""Meaning anchors: the parts of a text a rewrite is not allowed to move.

An anchor is anything whose change would make the rewrite *say something
else*: a number, a date, a name, a negation, a hedge that becomes a promise, a
quotation, a citation.  Style may move freely around them; they may not move.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Set

from wia.text.segment import sentences
from wia.text.tokens import words

# --- patterns --------------------------------------------------------------
_NUMBER_RE = re.compile(
    r"(?<![\w.])(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d+)?\s*(?:%|procent|percent|"
    r"euro|eur|€|\$|£|dollar|pond|k|m|mln|mrd|miljoen|miljard|million|billion)?(?![\w])",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2}|"
    r"\d{1,2}\s+(?:januari|februari|maart|april|mei|juni|juli|augustus|september|"
    r"oktober|november|december|january|february|march|april|may|june|july|august|"
    r"september|october|november|december)(?:\s+\d{4})?|"
    r"(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag|monday|tuesday|"
    r"wednesday|thursday|friday|saturday|sunday)|"
    r"Q[1-4]\b|\b(?:19|20)\d{2}\b)",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"\b\d{1,2}[:.]\d{2}\s*(?:uur|am|pm|u\.)?\b", re.IGNORECASE)
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+|\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_QUOTE_RE = re.compile(r"[\"“”«»]([^\"“”«»]{4,300})[\"“”«»]|'([^']{8,300})'")
_CITATION_RE = re.compile(r"\(([^)]{2,40}?,\s*(?:19|20)\d{2}[a-z]?)\)")
_CODEISH_RE = re.compile(r"`[^`]+`|\b\w+_\w+\b|\b[a-z]+[A-Z]\w*\b|\b\w+\(\)")
_ORDER_ID_RE = re.compile(r"\b[A-Z0-9]{2,}[-–][A-Z0-9]{2,}\b|\b\d{4,}\b")

NEGATIONS: Dict[str, Set[str]] = {
    "nl": {"niet", "geen", "nooit", "niks", "niets", "zonder", "nergens", "noch",
           "evenmin", "onmogelijk", "weiger", "weigeren"},
    "en": {"not", "no", "never", "none", "nothing", "without", "neither", "nor",
           "cannot", "can't", "won't", "don't", "doesn't", "didn't", "isn't",
           "aren't", "wasn't", "weren't", "impossible", "refuse", "refuses"},
}

# Words that carry how *sure* the writer is. Turning "may" into "will" changes
# the claim as surely as changing a number does.
CERTAINTY: Dict[str, Dict[str, float]] = {
    "nl": {
        "misschien": 0.3, "mogelijk": 0.35, "wellicht": 0.3, "waarschijnlijk": 0.6,
        "vermoedelijk": 0.5, "kan": 0.45, "kunnen": 0.45, "zou": 0.4, "zouden": 0.4,
        "lijkt": 0.4, "ongeveer": 0.5, "circa": 0.5, "rond": 0.5, "meestal": 0.6,
        "vaak": 0.6, "altijd": 0.95, "zeker": 0.9, "zal": 0.85, "zullen": 0.85,
        "moet": 0.9, "moeten": 0.9, "is": 0.85, "wordt": 0.85, "nooit": 0.95,
        "gegarandeerd": 1.0, "uiteraard": 0.9,
    },
    "en": {
        "maybe": 0.3, "perhaps": 0.3, "possibly": 0.35, "probably": 0.6,
        "likely": 0.6, "may": 0.45, "might": 0.4, "could": 0.4, "would": 0.45,
        "seems": 0.4, "appears": 0.4, "roughly": 0.5, "approximately": 0.5,
        "about": 0.5, "around": 0.5, "usually": 0.6, "often": 0.6,
        "always": 0.95, "certainly": 0.9, "definitely": 0.95, "will": 0.85,
        "must": 0.9, "is": 0.85, "are": 0.85, "never": 0.95, "guaranteed": 1.0,
    },
}

_STOP_CAPS = {
    "de", "het", "een", "en", "of", "maar", "the", "a", "an", "and", "or", "but",
    "in", "on", "at", "to", "for", "with", "van", "in", "op", "met", "voor",
    "ik", "we", "wij", "je", "u", "i", "we", "you", "they", "he", "she", "it",
    "this", "that", "these", "those", "dit", "dat", "deze", "die", "er", "there",
    "als", "if", "when", "wanneer", "na", "before", "voor", "onze", "our", "my",
    "mijn", "zijn", "haar", "his", "her", "their", "hun", "hi", "hallo", "hoi",
    "beste", "geachte", "dear", "sorry", "bedankt", "thanks", "thank",
    "wat", "what", "how", "hoe", "why", "waarom", "who", "wie", "which",
    "welke", "yes", "no", "ja", "nee", "ok", "okay", "oke", "let", "lets",
    "kind", "best", "yours", "groet", "groeten", "note", "let op", "update",
}


@dataclass
class Anchors:
    numbers: List[str] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    times: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    quotes: List[str] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    identifiers: List[str] = field(default_factory=list)
    technical: List[str] = field(default_factory=list)
    negation_count: int = 0
    certainty: float = 0.0
    sentence_polarity: List[bool] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "numbers": self.numbers, "dates": self.dates, "times": self.times,
            "entities": self.entities, "quotes": self.quotes,
            "citations": self.citations, "urls": self.urls,
            "identifiers": self.identifiers, "technical": self.technical,
            "negation_count": self.negation_count,
            "certainty": round(self.certainty, 4),
        }


def _norm_number(raw: str) -> str:
    """Normalise so ``1.200`` (nl) and ``1,200`` (en) compare equal."""
    s = raw.strip().lower().replace(" ", "")
    s = s.replace("procent", "%").replace("percent", "%").replace("euro", "€")
    core = re.match(r"^[\d.,]+", s)
    if core:
        digits = core.group(0)
        # Strip thousands separators, keep one decimal separator as '.'
        if digits.count(",") == 1 and (len(digits.split(",")[-1]) <= 2):
            digits = digits.replace(".", "").replace(",", ".")
        else:
            digits = digits.replace(",", "")
            if digits.count(".") > 1:
                digits = digits.replace(".", "")
        try:
            value = float(digits)
            digits = str(int(value)) if value == int(value) else f"{value:.4f}".rstrip("0")
        except ValueError:
            pass
        s = digits + s[core.end():]
    return s


def extract_anchors(text: str, language: str = "en") -> Anchors:
    lang = "nl" if str(language).startswith("nl") else "en"
    a = Anchors()

    # Masking order matters: a reference number must not be shredded into two
    # bare numbers, and a date must not contribute a stray "14".
    a.urls = sorted({m.group(0) for m in _URL_RE.finditer(text)})
    masked = _URL_RE.sub(" ", text)

    a.citations = sorted({m.group(1) for m in _CITATION_RE.finditer(masked)})
    a.technical = sorted({m.group(0) for m in _CODEISH_RE.finditer(masked)})

    a.identifiers = sorted({
        m.group(0) for m in _ORDER_ID_RE.finditer(masked)
        if "-" in m.group(0) or "–" in m.group(0) or len(m.group(0)) > 4
    })
    for ident in a.identifiers:
        masked = masked.replace(ident, " ")

    date_spans = [m.group(0) for m in _DATE_RE.finditer(masked)]
    time_spans = [m.group(0) for m in _TIME_RE.finditer(masked)]
    a.dates = sorted({d.lower() for d in date_spans})
    a.times = sorted({t.lower().replace(" ", "") for t in time_spans})
    number_source = masked
    for hit in sorted(set(date_spans) | set(time_spans), key=len, reverse=True):
        number_source = re.sub(re.escape(hit), " ", number_source, flags=re.IGNORECASE)
    a.numbers = sorted({_norm_number(m.group(0)) for m in _NUMBER_RE.finditer(number_source)
                        if any(ch.isdigit() for ch in m.group(0))})
    a.quotes = sorted({(m.group(1) or m.group(2) or "").strip()
                       for m in _QUOTE_RE.finditer(masked)} - {""})

    # Entities, in two passes.  A capital at the start of a sentence is not
    # evidence of anything — every sentence has one — so only capitals in
    # mid-sentence position establish that a token is a name.  Sentence-initial
    # tokens are then admitted only if they were established that way.
    #
    # Getting this wrong is expensive: a rewrite that turns "It is" into "It's"
    # would otherwise look like it invented a person called It's, and the
    # meaning guard would reject a perfectly good rewrite.
    strong: Set[str] = set()
    initial: Set[str] = set()
    for seg in sentences(masked):
        toks = seg.text.split()
        for i, tok in enumerate(toks):
            core = tok.strip(".,;:!?()[]\"'“”‘’")
            if len(core) < 2 or not core[:1].isupper() or core.lower() in _STOP_CAPS:
                continue
            if core.isupper() and len(core) <= 4:
                strong.add(core)  # acronym
                continue
            (initial if i == 0 else strong).add(core)
    a.entities = sorted(strong | (initial & strong))

    negs = NEGATIONS[lang]
    toks = words(masked)
    a.negation_count = sum(1 for t in toks if t in negs)
    a.sentence_polarity = [
        any(w in negs for w in words(s.text)) for s in sentences(masked)
    ]

    cert = CERTAINTY[lang]
    hits = [cert[t] for t in toks if t in cert]
    a.certainty = sum(hits) / len(hits) if hits else 0.5
    return a
