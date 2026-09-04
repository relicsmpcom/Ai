"""Redundancy reduction.

Cutting is the operation with the highest risk of losing meaning, so every cut
here is narrow and conditional: stock phrases that carry no information, and
sentences that restate the immediately preceding one almost word for word.
Anything less obvious is left alone and reported instead.
"""

from __future__ import annotations

import re
from typing import List

from wia.humanizer.context import Context
from wia.humanizer.ops.registry import op
from wia.lang import function_words
from wia.text.segment import sentences as split_sentences
from wia.text.tokens import words as tokenize

_CLOSERS = {
    "en": (
        r"^in conclusion\b", r"^to summari[sz]e\b", r"^all in all\b",
        r"^ultimately[, ]", r"^in summary\b", r"^overall, it (is|can be)\b",
    ),
    "nl": (
        r"^kortom\b", r"^samenvattend\b", r"^concluderend\b",
        r"^al met al\b", r"^tot slot\b",
    ),
}


@op("drop_stock_phrases", "Remove phrases that add words but no information.",
    order=20, group="redundancy")
def drop_stock_phrases(text: str, ctx: Context) -> str:
    empties = [k for k, v in ctx.lex.get("simplify", {}).items() if v == ""]
    for phrase in sorted(empties, key=len, reverse=True):
        pattern = re.compile(rf"{re.escape(phrase)}[,:]?\s*", re.IGNORECASE)

        def sub(m: re.Match) -> str:
            ctx.log("drop_stock_phrases", m.group(0).strip(), "",
                    "phrase carried no information")
            return ""

        text = pattern.sub(sub, text)
    text = re.sub(r"\s{2,}", " ", text)
    return re.sub(r"(^|[.!?…]\s+|\n\s*)([a-z])",
                  lambda m: m.group(1) + m.group(2).upper(), text)


@op("drop_restated_sentences", "Remove a sentence that repeats its neighbour.",
    order=21, group="redundancy")
def drop_restated_sentences(text: str, ctx: Context) -> str:
    segs = split_sentences(text)
    if len(segs) < 3:
        return text
    fw = function_words(ctx.language)
    keep: List[str] = []
    previous: set[str] = set()
    for seg in segs:
        content = {w for w in tokenize(seg.text) if w not in fw and len(w) > 3}
        if previous and content:
            overlap = len(content & previous) / len(content | previous)
            # Near-identical content *and* no new numbers or names.
            if overlap >= 0.62 and not re.search(r"\d", seg.text):
                ctx.log("drop_restated_sentences", seg.text[:70], "",
                        f"restates the previous sentence ({overlap:.0%} overlap)")
                continue
        keep.append(seg.text)
        previous = content
    if len(keep) == len(segs):
        return text
    from wia.humanizer.ops.sentences import _rejoin

    return _rejoin(text, keep)


@op("trim_summary_close", "Drop a closing sentence that only restates the text.",
    order=22, group="redundancy")
def trim_summary_close(text: str, ctx: Context) -> str:
    if ctx.options.purpose == "summarize":
        return text  # a summary is allowed to summarise
    segs = split_sentences(text)
    if len(segs) < 4:
        return text
    last = segs[-1].text.strip()
    patterns = _CLOSERS["nl" if ctx.is_nl else "en"]
    if not any(re.search(p, last, re.IGNORECASE) for p in patterns):
        return text
    if re.search(r"\d", last):
        return text  # it carries a figure; that is content, not filler
    fw = function_words(ctx.language)
    body = {w for s in segs[:-1] for w in tokenize(s.text) if w not in fw and len(w) > 3}
    close = {w for w in tokenize(last) if w not in fw and len(w) > 3}
    if close and len(close & body) / len(close) >= 0.6:
        ctx.log("trim_summary_close", last[:70], "",
                "closing sentence only restated what came before")
        from wia.humanizer.ops.sentences import _rejoin

        return _rejoin(text, [s.text for s in segs[:-1]])
    return text
