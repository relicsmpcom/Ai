"""A parsed view of one text, computed once and shared by every feature."""

from __future__ import annotations

import re
import zlib
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property
from typing import List

from wia.lang import function_words
from wia.text import paragraphs, sentences
from wia.text.tokens import mean, punctuation, stdev, syllables, word_tokens, words
from wia.types import Language, Segment


@dataclass
class Doc:
    text: str
    language: str = "en"

    def __post_init__(self) -> None:
        if isinstance(self.language, Language):
            self.language = self.language.value

    # -- structure ---------------------------------------------------------
    @cached_property
    def sentences(self) -> List[Segment]:
        return sentences(self.text)

    @cached_property
    def paragraphs(self) -> List[Segment]:
        return paragraphs(self.text)

    @cached_property
    def sentence_words(self) -> List[List[str]]:
        return [words(s.text) for s in self.sentences]

    @cached_property
    def sentence_lengths(self) -> List[int]:
        return [len(w) for w in self.sentence_words if w]

    @cached_property
    def words(self) -> List[str]:
        return words(self.text)

    @cached_property
    def surface_tokens(self) -> List[str]:
        return word_tokens(self.text)

    @cached_property
    def word_counts(self) -> Counter:
        return Counter(self.words)

    @cached_property
    def bigrams(self) -> List[str]:
        w = self.words
        return [f"{a} {b}" for a, b in zip(w, w[1:])]

    @cached_property
    def trigrams(self) -> List[str]:
        w = self.words
        return [f"{a} {b} {c}" for a, b, c in zip(w, w[1:], w[2:])]

    @cached_property
    def lowered(self) -> str:
        return self.text.lower()

    @cached_property
    def function_words(self):
        return function_words(self.language)

    @cached_property
    def punctuation(self) -> List[str]:
        return punctuation(self.text)

    @cached_property
    def syllable_counts(self) -> List[int]:
        return [syllables(w) for w in self.words]

    # -- convenience -------------------------------------------------------
    @property
    def n_words(self) -> int:
        return len(self.words)

    @property
    def n_sentences(self) -> int:
        return max(1, len(self.sentence_lengths))

    @property
    def n_paragraphs(self) -> int:
        return max(1, len(self.paragraphs))

    def rate(self, count: float, per: int = 100) -> float:
        """Occurrences per ``per`` words — the standard normalisation here."""
        return count / max(1, self.n_words) * per

    @cached_property
    def phrase_haystack(self) -> str:
        """Lower-cased text with punctuation turned into spaces.

        Matching " furthermore " against the raw text misses every
        "Furthermore," in the corpus — which is most of them. Normalising the
        haystack once is the difference between a feature that measures
        connective density and one that measures how often a writer forgot the
        comma.
        """
        flattened = re.sub(r"[^\w'’\s-]+", " ", self.lowered)
        return " " + re.sub(r"\s+", " ", flattened) + " "

    def phrase_count(self, phrases) -> int:
        hay = self.phrase_haystack
        return sum(hay.count(f" {p} ") for p in phrases)

    @cached_property
    def compression_ratio(self) -> float:
        raw = self.text.encode("utf-8")
        if len(raw) < 40:
            return 1.0
        return len(zlib.compress(raw, 6)) / len(raw)

    def mean_sentence_length(self) -> float:
        return mean(self.sentence_lengths)

    def sd_sentence_length(self) -> float:
        return stdev(self.sentence_lengths)
