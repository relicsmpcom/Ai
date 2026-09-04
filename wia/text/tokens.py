"""Word-level tokenisation for Dutch and English.

Deliberately dependency-free.  Dutch needs a few things a naive ``\\w+`` split
gets wrong: the elided article ``'t``/``'n``/``'s``, hyphenated compounds
(``coronavirus-maatregelen``), and the genitive ``Jan's``.  English needs
contractions kept whole (``don't``, ``it's``, ``o'clock``).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List

# A word is a run of letters, optionally joined by internal apostrophes or
# hyphens, and may *start* with an apostrophe ('t kofschip, 'n keer).
WORD_RE = re.compile(
    r"['’]?[^\W\d_]+(?:['’\-][^\W\d_]+)*|\d+(?:[.,]\d+)*%?",
    re.UNICODE,
)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"[ \t ]+")


def normalize_whitespace(text: str) -> str:
    """Collapse horizontal whitespace, normalise newlines, keep paragraphs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_RE.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def word_tokens(text: str) -> List[str]:
    """Surface tokens, original casing preserved."""
    return WORD_RE.findall(text)


def words(text: str) -> List[str]:
    """Lower-cased alphabetic-ish tokens, the unit most features count in."""
    return [w.lower() for w in WORD_RE.findall(text)]


def strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn"
    )


def punctuation(text: str) -> List[str]:
    return _PUNCT_RE.findall(text)


_VOWELS = "aeiouyàáâäèéêëìíîïòóôöùúûüij"


def syllables(word: str) -> int:
    """Cheap syllable estimate that works acceptably for both NL and EN.

    Used only for readability indices, where a systematic small bias is
    harmless because we compare texts against each other, not against an
    absolute grade level.
    """
    w = strip_accents(word.lower())
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return 0
    count, prev_vowel = 0, False
    for ch in w:
        is_vowel = ch in "aeiouy"
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    # Silent trailing -e is common in English, rare but real in Dutch loanwords.
    if w.endswith("e") and count > 1 and not w.endswith(("le", "ee", "ie")):
        count -= 1
    return max(1, count)


def mean(values: Iterable[float], default: float = 0.0) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else default


def stdev(values: Iterable[float], default: float = 0.0) -> float:
    vals = list(values)
    if len(vals) < 2:
        return default
    m = sum(vals) / len(vals)
    var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    return var ** 0.5
