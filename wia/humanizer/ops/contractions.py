"""Contraction control.

English has a regular clitic system, so this is mostly table-driven.  Dutch
does not: ``'t``, ``'n`` and ``zo'n`` are real, but they are register markers
rather than a general rule, and applying them mechanically produces text that
reads as a foreigner imitating informality.  So Dutch gets a short, careful
list and a lower rate.
"""

from __future__ import annotations

import re
from typing import Dict

from wia.features.lexicons import EN_CONTRACTIONS
from wia.humanizer.context import Context
from wia.humanizer.ops.registry import op

LEVEL_RATE: Dict[str, float] = {
    "none": 0.0, "light": 0.35, "normal": 0.75, "conversational": 1.0,
}

# Dutch reductions that a native writer actually uses in running prose.
NL_REDUCTIONS = (
    (r"\bzo een\b", "zo'n"),
    (r"\bhet is\b", "'t is"),
    (r"\bnaar toe\b", "naartoe"),
    (r"\bmoet je\b", "moet je"),
)

# The reverse direction, for formal registers.
EN_EXPANSIONS = {v.lower(): k for k, v in EN_CONTRACTIONS.items()}


@op("apply_contractions", "Contract where the register allows it.", order=60,
    group="register")
def apply_contractions(text: str, ctx: Context) -> str:
    o = ctx.options
    rate = LEVEL_RATE.get(o.contractions, 0.75)
    if o.formality >= 5:
        rate = 0.0
    if rate <= 0:
        return text

    if ctx.is_nl:
        # Dutch: sparing, and only in genuinely informal registers.
        if o.formality > 2:
            return text
        for pattern, replacement in NL_REDUCTIONS:
            def sub(m: re.Match, replacement: str = replacement) -> str:
                if not ctx.chance(rate * 0.4):
                    return m.group(0)
                ctx.log("apply_contractions", m.group(0), replacement,
                        "informal Dutch reduction")
                return replacement

            text = re.sub(pattern, sub, text, flags=re.IGNORECASE)
        return text

    for expansion, contraction in sorted(EN_CONTRACTIONS.items(), key=lambda kv: -len(kv[0])):
        pattern = re.compile(rf"(?<![\w'’]){re.escape(expansion)}(?![\w'’])", re.IGNORECASE)

        def sub(m: re.Match, contraction: str = contraction) -> str:
            if not ctx.chance(rate):
                return m.group(0)
            out = contraction
            if m.group(0)[:1].isupper():
                out = out[0].upper() + out[1:]
            ctx.log("apply_contractions", m.group(0), out, "contracted form reads naturally")
            return out

        text = pattern.sub(sub, text)
    return text


@op("expand_contractions", "Expand contractions for formal registers.", order=61,
    group="register")
def expand_contractions(text: str, ctx: Context) -> str:
    if ctx.is_nl or ctx.options.formality < 5:
        return text
    for contraction, expansion in EN_EXPANSIONS.items():
        pattern = re.compile(rf"(?<![\w'’]){re.escape(contraction)}(?![\w'’])", re.IGNORECASE)

        def sub(m: re.Match, expansion: str = expansion) -> str:
            out = expansion
            if m.group(0)[:1].isupper():
                out = out[0].upper() + out[1:]
            ctx.log("expand_contractions", m.group(0), out, "formal register")
            return out

        text = pattern.sub(sub, text)
    return text
