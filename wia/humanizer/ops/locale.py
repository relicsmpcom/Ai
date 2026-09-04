"""Locale matching: spelling and regional vocabulary.

Only spelling and clearly regional lexis are touched.  Dates, currency and
number formats are *not* rewritten: changing "14/03" to "03/14" is a meaning
change wearing a locale costume, and the guard would rightly reject it.
"""

from __future__ import annotations

import re

from wia.humanizer.context import Context
from wia.humanizer.ops.registry import op


@op("apply_locale", "Match spelling and regional vocabulary to the locale.",
    order=80, group="locale")
def apply_locale(text: str, ctx: Context) -> str:
    table = (ctx.lex.get("locale") or {}).get(ctx.locale)
    if not table:
        return text
    table = _expand_inflections(table)
    for source, target in sorted(table.items(), key=lambda kv: -len(kv[0])):
        pattern = re.compile(rf"(?<![\w'’]){re.escape(source)}(?![\w'’])", re.IGNORECASE)

        def sub(m: re.Match, target: str = target) -> str:
            out = target
            if m.group(0)[:1].isupper():
                out = out[0].upper() + out[1:]
            if m.group(0).isupper():
                out = out.upper()
            ctx.log("apply_locale", m.group(0), out, f"{ctx.locale} spelling")
            return out

        text = pattern.sub(sub, text)
    return text


_SUFFIXES = ("s", "d", "r", "rs", "ment", "ments")


def _expand_inflections(table: dict) -> dict:
    """Cover the inflected forms of each pair without listing them by hand.

    ``organize → organise`` should also fix *organizes*, *organized*,
    *organizing*, *organization(s)*; a spelling table that only handles the
    bare stem leaves half the text in the wrong variety.
    """
    out = dict(table)
    for source, target in table.items():
        for suffix in _SUFFIXES:
            out.setdefault(source + suffix, target + suffix)
        if source.endswith("e") and target.endswith("e"):
            out.setdefault(source[:-1] + "ing", target[:-1] + "ing")
            out.setdefault(source[:-1] + "ed", target[:-1] + "ed")
        if source.endswith("ize") and target.endswith("ise"):
            stem_s, stem_t = source[:-3], target[:-3]
            out.setdefault(stem_s + "ization", stem_t + "isation")
            out.setdefault(stem_s + "izations", stem_t + "isations")
        if source.endswith("ise") and target.endswith("ize"):
            stem_s, stem_t = source[:-3], target[:-3]
            out.setdefault(stem_s + "isation", stem_t + "ization")
            out.setdefault(stem_s + "isations", stem_t + "izations")
    return out
