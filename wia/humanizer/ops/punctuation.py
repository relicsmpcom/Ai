"""Punctuation habits.

Small, safe changes only.  Punctuation is part of a writer's fingerprint, so
these operations run at low rates and skip entirely when a style profile says
the writer genuinely favours the mark in question.
"""

from __future__ import annotations

import re

from wia.humanizer.context import Context
from wia.humanizer.ops.registry import op


@op("normalize_dashes", "Convert display dashes into ordinary punctuation.",
    order=64, group="punctuation")
def normalize_dashes(text: str, ctx: Context) -> str:
    if ctx.style is not None and ctx.style.punctuation.get("em_dash", 0) > 0.4:
        return text  # the writer uses dashes; leave them alone
    def sub(m: re.Match) -> str:
        if not ctx.chance(0.7):
            return m.group(0)
        ctx.log("normalize_dashes", m.group(0).strip(), ",", "display dash replaced")
        return ", "

    return re.sub(r"\s+[—–]\s+", sub, text)


@op("reduce_semicolons", "Turn a semicolon into a full stop.", order=65,
    group="punctuation")
def reduce_semicolons(text: str, ctx: Context) -> str:
    if ctx.options.formality >= 5:
        return text
    if ctx.style is not None and ctx.style.punctuation.get("semicolon", 0) > 0.3:
        return text

    def sub(m: re.Match) -> str:
        if not ctx.chance(0.6):
            return m.group(0)
        ctx.log("reduce_semicolons", ";", ".", "semicolon split into two sentences")
        return ". " + m.group(1).upper()

    return re.sub(r";\s+(\w)", sub, text)


@op("tidy_spacing", "Fix spacing and duplicated punctuation.", order=95,
    group="punctuation")
def tidy_spacing(text: str, ctx: Context) -> str:
    out = re.sub(r"[ \t]{2,}", " ", text)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    out = re.sub(r"([,;:])(?=[^\s\d])", r"\1 ", out)
    out = re.sub(r"\.{4,}", "...", out)
    out = re.sub(r"([.!?])\s*,\s*", r"\1 ", out)
    out = re.sub(r",\s*([.!?])", r"\1", out)
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"([.!?])\1{2,}", r"\1", out)
    out = re.sub(r"\s+$", "", out, flags=re.MULTILINE)
    return out.strip()


_VOWEL_SOUND = re.compile(r"^(?:a|e|i|o|u|hour|honest|honou?r|heir)", re.IGNORECASE)
_CONSONANT_EXCEPTIONS = re.compile(r"^(?:uni|use|user|usual|euro|one|once)", re.IGNORECASE)


@op("fix_articles", "Repair a/an after a word was replaced.", order=96,
    group="punctuation")
def fix_articles(text: str, ctx: Context) -> str:
    """A rewrite that turns "a crucial role" into "a important role" is a bug."""
    if ctx.is_nl:
        return text

    def sub(m: re.Match) -> str:
        article, gap, word = m.group(1), m.group(2), m.group(3)
        vowel = bool(_VOWEL_SOUND.match(word)) and not _CONSONANT_EXCEPTIONS.match(word)
        correct = "an" if vowel else "a"
        if article.lower() == correct:
            return m.group(0)
        out = correct.capitalize() if article[0].isupper() else correct
        return f"{out}{gap}{word}"

    # Case-insensitive: a sentence-initial "A" needs fixing just as much
    # as a mid-sentence "a", and it is the one readers notice.
    return re.sub(r"\b(an?)(\s+)([A-Za-z][\w'-]*)", sub, text, flags=re.IGNORECASE)


@op("fix_sentence_case", "Restore capitals that an edit knocked off.", order=97,
    group="punctuation")
def fix_sentence_case(text: str, ctx: Context) -> str:
    """Re-capitalise sentence starts — but only if the author capitalised theirs.

    Some people write in lower case on purpose. Forcing capitals on them would
    be the humanizer overwriting a voice instead of preserving it, so this runs
    only when the original text had no lower-case sentence openings.
    """
    from wia.text.segment import sentences

    if ctx.original:
        original_lower = sum(1 for s in sentences(ctx.original) if s.text[:1].islower())
        if original_lower:
            return text

    def sub(m: re.Match) -> str:
        return m.group(1) + m.group(2).upper()

    return re.sub(r"(^|[.!?…]\s+|\n\s*)([a-z])", sub, text)


_NL_COORDINATORS = ("En", "Maar", "Want", "Of", "Dus")


@op("repair_dutch_word_order", "Undo verb-second inversion left by an edit.",
    order=94, group="general")
def repair_dutch_word_order(text: str, ctx: Context) -> str:
    """Dutch inverts subject and verb after a fronted element.

    Once an operation removes or replaces that fronted element, the inversion
    has to go with it. Any sentence still opening with a finite verb is a
    sentence this pipeline broke, so it is repaired here — and if it cannot be
    repaired confidently, it is left exactly as it was.
    """
    if not ctx.is_nl:
        return text
    from wia.humanizer.ops.dutch import (
        deinvert,
        is_inverted,
        repair_impersonal_passive,
    )
    from wia.text.segment import sentences

    out = text
    for seg in sentences(text):
        body = seg.text
        prefix = ""
        candidate = body
        for coordinator in _NL_COORDINATORS:
            if body.startswith(coordinator + " "):
                prefix = coordinator + " "
                candidate = body[len(prefix):]
                break
        if not is_inverted(candidate) or candidate.rstrip().endswith("?"):
            continue
        fixed = deinvert(candidate) or repair_impersonal_passive(candidate)
        if not fixed:
            continue
        if prefix:
            fixed = prefix + fixed[0].lower() + fixed[1:]
        ctx.log("repair_dutch_word_order", body[:60], fixed[:60],
                "verb-second order restored after an edit")
        out = out.replace(body, fixed, 1)
    return out
