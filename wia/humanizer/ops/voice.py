"""Voice, directness and register.

Note what is deliberately *absent*: nothing here adds an opinion, an anecdote
or a hedge that was not already in the text. "Personal voice" in this system
means preserving and surfacing the voice the author already used — never
inventing experiences on their behalf.
"""

from __future__ import annotations

import re
from typing import Tuple

from wia.humanizer.context import Context
from wia.humanizer.ops.registry import op

# (pattern, softer, sharper) — applied depending on the directness setting.
_DIRECTNESS_EN: Tuple[Tuple[str, str, str], ...] = (
    (r"\bI was wondering if you could\b", "I was wondering if you could", "Could you"),
    (r"\bwould it be possible (?:for you )?to\b", "would it be possible to", "can you"),
    (r"\bif you could\b", "if you could", "please"),
    (r"\bplease could you\b", "would you mind", "could you"),
    (r"\byou (?:need|have) to\b", "it would help if you could", "you need to"),
    (r"\byou must\b", "you may want to", "you must"),
    (r"\bwe require\b", "we would need", "we need"),
    (r"\bI think (?:that )?\b", "I think ", ""),
    (r"\bjust\s+", "just ", ""),
)
_DIRECTNESS_NL: Tuple[Tuple[str, str, str], ...] = (
    (r"\bzou u zo vriendelijk willen zijn om\b", "zou u zo vriendelijk willen zijn om", "kunt u"),
    (r"\bzou het mogelijk zijn om\b", "zou het mogelijk zijn om", "kunt u"),
    (r"\bwilt u alstublieft\b", "zou u willen", "wilt u"),
    (r"\bu (?:moet|dient)\b", "het zou helpen als u", "u moet"),
    (r"\bwij hebben nodig\b", "wij zouden graag", "wij hebben nodig"),
    (r"\bik denk dat\b", "ik denk dat", ""),
    (r"\bgewoon\s+", "gewoon ", ""),
)

_SOFT = {"diplomatic", "soft"}
_SHARP = {"direct", "very_direct"}


@op("adjust_directness", "Make requests softer or sharper as asked.", order=62,
    group="voice")
def adjust_directness(text: str, ctx: Context) -> str:
    mode = ctx.options.directness
    if mode == "balanced":
        return text
    table = _DIRECTNESS_NL if ctx.is_nl else _DIRECTNESS_EN
    for pattern, softer, sharper in table:
        target = softer if mode in _SOFT else sharper

        def sub(m: re.Match, target: str = target) -> str:
            if m.group(0).strip().lower() == target.strip().lower():
                return m.group(0)
            if not ctx.chance(0.8):
                return m.group(0)
            out = target
            if m.group(0)[:1].isupper() and out:
                out = out[0].upper() + out[1:]
            ctx.log("adjust_directness", m.group(0), out, f"directness set to {mode}")
            return out + (" " if out and not out.endswith(" ") and m.group(0).endswith(" ") else "")

        text = re.sub(pattern, sub, text, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text)


_JE_FORMS = {
    "je": "u", "jij": "u", "jou": "u", "jouw": "uw", "jullie": "u",
    "jezelf": "uzelf", "je eigen": "uw eigen",
}
_U_FORMS = {"u": "je", "uw": "je", "uzelf": "jezelf"}


@op("set_register", "Keep Dutch je/u consistent.", order=63, group="voice")
def set_register(text: str, ctx: Context) -> str:
    """Dutch second-person register must not wobble inside one text."""
    if not ctx.is_nl:
        return text
    lowered = text.lower()
    je_count = len(re.findall(r"\b(?:je|jij|jouw|jullie)\b", lowered))
    u_count = len(re.findall(r"\b(?:u|uw)\b", lowered))
    if je_count == 0 and u_count == 0:
        return text

    if ctx.options.formality >= 4:
        target = "u"
    elif ctx.options.formality <= 2:
        target = "je"
    else:
        target = "u" if u_count > je_count else "je"

    table = _JE_FORMS if target == "u" else _U_FORMS
    if target == "u" and je_count == 0:
        return text
    if target == "je" and u_count == 0:
        return text

    for source, replacement in sorted(table.items(), key=lambda kv: -len(kv[0])):
        pattern = re.compile(rf"(?<![\w'’]){re.escape(source)}(?![\w'’])", re.IGNORECASE)

        def sub(m: re.Match, replacement: str = replacement) -> str:
            out = replacement
            if m.group(0)[:1].isupper():
                out = out[0].upper() + out[1:]
            ctx.log("set_register", m.group(0), out, f"register unified to “{target}”")
            return out

        text = pattern.sub(sub, text)
    return text


@op("soften_imperatives", "Take the edge off bare commands when asked.",
    order=66, group="voice")
def soften_imperatives(text: str, ctx: Context) -> str:
    if ctx.options.directness not in _SOFT and ctx.options.tone != "empathetic":
        return text
    prefix = "Zou je " if ctx.is_nl else "Could you "
    pattern = re.compile(r"(^|\n)(Stuur|Send|Fix|Repareer|Doe|Do|Geef|Give)\s+", re.MULTILINE)

    def sub(m: re.Match) -> str:
        if not ctx.chance(0.5):
            return m.group(0)
        verb = m.group(2).lower()
        out = f"{m.group(1)}{prefix}{verb} "
        ctx.log("soften_imperatives", m.group(0).strip(), out.strip(),
                "bare command softened")
        return out

    return pattern.sub(sub, text)
