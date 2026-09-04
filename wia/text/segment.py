"""Sentence / paragraph / window segmentation with NL+EN abbreviation guards.

Segment offsets always index back into the *original* string so the UI can
paint a heatmap over the text the user actually pasted.
"""

from __future__ import annotations

import re
from typing import List

from wia.types import Segment

# Abbreviations that end in a period without ending a sentence.
_ABBREV = {
    # Dutch
    "bijv", "bv", "bijz", "blz", "ca", "cf", "dhr", "dwz", "d.w.z", "e.d", "enz",
    "evt", "excl", "incl", "ihb", "ipv", "i.p.v", "jl", "mbt", "m.b.t", "mevr",
    "mej", "mln", "mrd", "mv", "nl", "nr", "o.a", "oa", "ong", "pag", "resp",
    "t.o.v", "tov", "t.a.v", "tav", "vgl", "zgn", "z.g.n", "drs", "ir", "ing",
    "mr", "prof", "st", "vs", "etc", "aug", "sept", "okt", "dec", "jan", "feb",
    # English
    "mrs", "ms", "dr", "jr", "sr", "e.g", "eg", "i.e", "ie", "approx", "fig",
    "no", "vol", "pp", "ed", "al", "inc", "ltd", "co", "corp", "dept", "est",
    "min", "max", "avg", "univ", "assoc", "ave", "blvd",
}

_SENT_END = re.compile(r"([.!?…]+[)\]\"'”’]*)(\s+|$)")

#: Words that almost always start a new sentence rather than continue one.
#: They let "…at 9 a.m. She left" split while "Dhr. Jansen" stays whole.
#: Deliberately limited to pronouns and demonstratives — a determiner like
#: "De" is far more likely to be part of a Dutch surname than a new sentence.
_STRONG_STARTERS = {
    "She", "He", "It", "They", "We", "I", "You", "This", "These", "Those",
    "There", "However", "But",
    "Hij", "Zij", "Ze", "Wij", "Ik", "Jij", "Jullie", "Dit", "Deze", "Er",
    "Maar", "Toch",
}
_TRAILING_TOKEN = re.compile(r"([^\s.]+)\.$")
_PARA_SPLIT = re.compile(r"\n\s*\n")


def _is_abbreviation(chunk: str) -> bool:
    m = _TRAILING_TOKEN.search(chunk.strip())
    if not m:
        return False
    token = m.group(1).lower().strip("([\"'“‘")
    if token in _ABBREV:
        return True
    # Single initial: "J." in "J. Bakker", or dotted acronym "U.S."
    if re.fullmatch(r"[^\W\d_]", token):
        return True
    if re.fullmatch(r"(?:[^\W\d_]\.)+[^\W\d_]", token):
        return True
    # Numeric ordinal / decimal: "3." at the start of a list item, "1.5"
    return bool(token.isdigit())


def sentences(text: str, offset: int = 0) -> List[Segment]:
    """Split ``text`` into sentence segments.

    Newlines inside a paragraph do not end a sentence, but a hard paragraph
    break does — bullet lists and headings otherwise glue together.
    """
    out: List[Segment] = []
    if not text.strip():
        return out

    index = 0
    for para in _paragraph_spans(text):
        body = text[para[0] : para[1]]
        cursor = 0
        for m in _SENT_END.finditer(body):
            end = m.end(1)
            candidate = body[cursor:end]
            if _is_abbreviation(candidate) and not _starts_new_sentence(body, m.end()):
                continue
            seg_text = candidate.strip()
            if seg_text:
                start_in_body = cursor + (len(candidate) - len(candidate.lstrip()))
                out.append(
                    Segment(
                        index=index,
                        text=seg_text,
                        start=offset + para[0] + start_in_body,
                        end=offset + para[0] + start_in_body + len(seg_text),
                    )
                )
                index += 1
            cursor = m.end()
        tail = body[cursor:].strip()
        if tail:
            start_in_body = cursor + (len(body[cursor:]) - len(body[cursor:].lstrip()))
            out.append(
                Segment(
                    index=index,
                    text=tail,
                    start=offset + para[0] + start_in_body,
                    end=offset + para[0] + start_in_body + len(tail),
                )
            )
            index += 1
    return out


def _starts_new_sentence(body: str, position: int) -> bool:
    """True when what follows can only be the start of a new sentence."""
    following = body[position:].split()
    return bool(following) and following[0].strip(",.;:!?\"'“”‘’") in _STRONG_STARTERS


def _paragraph_spans(text: str) -> List[tuple[int, int]]:
    spans: List[tuple[int, int]] = []
    cursor = 0
    for m in _PARA_SPLIT.finditer(text):
        if text[cursor : m.start()].strip():
            spans.append((cursor, m.start()))
        cursor = m.end()
    if text[cursor:].strip():
        spans.append((cursor, len(text)))
    return spans or [(0, len(text))]


def paragraphs(text: str) -> List[Segment]:
    out: List[Segment] = []
    for i, (start, end) in enumerate(_paragraph_spans(text)):
        body = text[start:end]
        stripped = body.strip()
        lead = len(body) - len(body.lstrip())
        out.append(
            Segment(
                index=i,
                text=stripped,
                start=start + lead,
                end=start + lead + len(stripped),
                kind="paragraph",
            )
        )
    return out


def windows(text: str, target_words: int = 60, stride_words: int = 30) -> List[Segment]:
    """Overlapping sentence windows — the unit segment-level detection scores.

    A single sentence is far too little evidence for an authorship estimate, so
    the detector never scores one alone: it scores a sliding window of whole
    sentences and attributes the result back to the sentences inside it.
    """
    sents = sentences(text)
    if not sents:
        return []
    counts = [len(s.text.split()) for s in sents]
    out: List[Segment] = []
    i = 0
    idx = 0
    while i < len(sents):
        total = 0
        j = i
        while j < len(sents) and total < target_words:
            total += counts[j]
            j += 1
        window = sents[i:j]
        out.append(
            Segment(
                index=idx,
                text=text[window[0].start : window[-1].end],
                start=window[0].start,
                end=window[-1].end,
                kind="window",
            )
        )
        idx += 1
        if j >= len(sents):
            break
        # advance by ~stride_words
        advanced = 0
        while i < len(sents) and advanced < stride_words:
            advanced += counts[i]
            i += 1
    return out
