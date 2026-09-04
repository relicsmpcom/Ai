"""Transition handling.

The failure mode this fixes is not that "Furthermore" is a bad word.  It is
that a text using *Furthermore, Moreover, Additionally, In conclusion* in five
consecutive paragraphs reads like a form being filled in.  So the operation
works on distribution: it thins mechanical connectives out, varies what is
left, and never lets one replacement dominate.
"""

from __future__ import annotations

import re
from typing import Dict, List

from wia.humanizer.context import Context
from wia.humanizer.ops.registry import op
from wia.text.segment import sentences


#: Openers that do not take a comma when they start a sentence.
_CONJUNCTIONS = {"and", "but", "so", "or", "yet", "en", "maar", "dus", "of", "want"}


def _style_for(ctx: Context) -> str:
    o = ctx.options
    if o.tone in ("academic",) or o.formality >= 6:
        return "academic"
    if o.tone in ("casual", "friendly", "humorous") or o.formality <= 2:
        return "conversational"
    if o.purpose in ("entertain",) or o.tone == "warm":
        return "narrative"
    if o.directness in ("very_direct", "direct") and o.formality <= 3:
        return "direct"
    return "professional"


@op("vary_transitions", "Thin out and vary mechanical connectives.", order=30,
    group="transitions")
def vary_transitions(text: str, ctx: Context) -> str:
    table: Dict[str, List[str]] = ctx.lex.get("mechanical_transitions", {})
    if not table:
        return text
    style = _style_for(ctx)
    pool = list(ctx.lex.get("transitions", {}).get(style, []))
    used: set[str] = set()

    # Replace longest phrases first so "in addition" is not eaten by "addition".
    for phrase in sorted(table, key=len, reverse=True):
        alternatives = [a for a in table[phrase] if a not in used]
        pattern = re.compile(
            rf"(^|(?<=[.!?…]\s)|(?<=\n))({re.escape(phrase)})(,?\s+)",
            re.IGNORECASE | re.MULTILINE,
        )

        def replace(m: re.Match) -> str:
            if not ctx.chance(0.85):
                return m.group(0)
            options = alternatives or pool
            if not options:
                return m.group(0)
            choice = ctx.rng.choice(options)
            used.add(choice)
            lead = m.group(1)
            if not choice:
                # Dropping the connective entirely: the sentence usually reads
                # better without it, so keep the following word capitalised.
                return lead
            # Coordinating conjunctions open a sentence without a comma;
            # English adverbial connectives take one.  Dutch does not comma off
            # a fronted adverbial — "Bovendien, speelt…" is not Dutch.
            if ctx.is_nl or choice.lower() in _CONJUNCTIONS:
                tail = " "
            else:
                tail = ", "
            replacement = choice[0].upper() + choice[1:] if lead != " " else choice
            ctx.log("vary_transitions", m.group(2), choice,
                    "mechanical connective varied")
            return f"{lead}{replacement}{tail}"

        text = pattern.sub(replace, text)

    return _fix_capitalisation(text)


#: Opener families too varied to list one by one.
_OPENER_FAMILIES = {
    "en": re.compile(
        r"(^|(?<=[.!?…]\s)|(?<=\n))(In (?:today's|this|the|an?) "
        r"(?:[\w-]+\s+){0,3}(?:world|landscape|era|environment|age|climate|society|market))"
        r",\s+", re.IGNORECASE | re.MULTILINE),
    "nl": re.compile(
        r"(^|(?<=[.!?…]\s)|(?<=\n))(In (?:de|het|deze|dit) "
        r"(?:[\w-]+\s+){0,3}(?:wereld|landschap|tijd|tijdperk|omgeving|markt|maatschappij))"
        r",\s+", re.IGNORECASE | re.MULTILINE),
}


@op("drop_empty_openers", "Remove openers that carry no information.", order=25,
    group="transitions")
def drop_empty_openers(text: str, ctx: Context) -> str:
    family = _OPENER_FAMILIES["nl" if ctx.is_nl else "en"]

    def drop_family(m: re.Match) -> str:
        ctx.log("drop_empty_openers", m.group(2), "", "scene-setting opener said nothing")
        return m.group(1)

    text = family.sub(drop_family, text)
    for opener in ctx.lex.get("openers", {}).get("drop", []):
        pattern = re.compile(
            rf"(^|(?<=[.!?…]\s)|(?<=\n))({re.escape(opener)})(,?\s+)",
            re.IGNORECASE | re.MULTILINE,
        )

        def replace(m: re.Match) -> str:
            ctx.log("drop_empty_openers", m.group(2), "", "opener carried no meaning")
            return m.group(1)

        text = pattern.sub(replace, text)
    return _fix_capitalisation(text)


@op("limit_transition_repeats", "Stop any single connective from taking over.",
    order=32, group="transitions")
def limit_transition_repeats(text: str, ctx: Context) -> str:
    """If one connective opens three or more sentences, replace the extras."""
    style = _style_for(ctx)
    pool = list(ctx.lex.get("transitions", {}).get(style, []))
    if not pool:
        return text
    counts: Dict[str, int] = {}
    segs = sentences(text)
    for seg in segs:
        first = seg.text.split(",")[0].strip().lower()
        if len(first.split()) <= 3:
            counts[first] = counts.get(first, 0) + 1

    overused = {k for k, v in counts.items() if v >= 3 and k}
    if not overused:
        return text

    out = text
    for phrase in overused:
        seen = 0
        pattern = re.compile(
            rf"(^|(?<=[.!?…]\s)|(?<=\n))({re.escape(phrase)})(,\s+)",
            re.IGNORECASE | re.MULTILINE,
        )

        def replace(m: re.Match) -> str:
            nonlocal seen
            seen += 1
            if seen <= 1:
                return m.group(0)
            choice = ctx.rng.choice(pool)
            ctx.log("limit_transition_repeats", m.group(2), choice,
                    "same opener used three times or more")
            separator = " " if (ctx.is_nl or choice.lower() in _CONJUNCTIONS) else ", "
            return f"{m.group(1)}{choice[0].upper() + choice[1:]}{separator}"

        out = pattern.sub(replace, out)
    return out


_SENTENCE_START_RE = re.compile(r"(^|[.!?…]\s+|\n\s*)([a-z])")


def _fix_capitalisation(text: str) -> str:
    """Re-capitalise sentence starts after a connective was removed."""
    return _SENTENCE_START_RE.sub(lambda m: m.group(1) + m.group(2).upper(), text)
