"""Vocabulary naturalisation.

Three separate jobs that are easy to confuse:

* *simplifying* — replacing an inflated word with the ordinary one;
* *formalising* — the reverse, when the target register asks for it;
* *softening* — taking the air out of superlatives without changing the claim.

Only the first and third run by default.  Formalising runs when the requested
formality is genuinely high, because upgrading someone's vocabulary uninvited
is how a humanizer ends up sounding like the thing it is supposed to fix.
"""

from __future__ import annotations

import re
from typing import Dict

from wia.humanizer.context import Context
from wia.humanizer.ops.registry import op

_WORD_BOUNDARY = r"(?<![\w'’-]){}(?![\w'’-])"


def _apply_map(text: str, mapping: Dict[str, object], ctx: Context, name: str,
               reason: str, probability: float = 0.9) -> str:
    """Apply a replacement table.

    A value may be a single word or a list of alternatives.  Lists exist so
    that softening three superlatives in one paragraph does not produce
    "important" three times — which is its own kind of machine-writing tell.
    """
    used: set = set()
    for source in sorted(mapping, key=len, reverse=True):
        raw = mapping[source]
        if isinstance(raw, list):
            fresh = [x for x in raw if x not in used] or raw
            target = ctx.rng.choice(fresh)
            used.add(target)
        else:
            target = raw
        # When a phrase is deleted outright, take its trailing comma with it —
        # otherwise "In conclusion, embracing…" becomes ", embracing…".
        tail = r"[,:]?\s*" if target == "" else ""
        pattern = re.compile(
            _WORD_BOUNDARY.format(re.escape(source)) + tail, re.IGNORECASE)

        def replace(m: re.Match) -> str:
            if not ctx.chance(probability):
                return m.group(0)
            original = m.group(0)
            if not target:
                return ""
            out = target
            if original[:1].isupper():
                out = out[0].upper() + out[1:]
            ctx.log(name, original, out, reason)
            return out

        text = pattern.sub(replace, text)
    return re.sub(r"\s{2,}", " ", text)


@op("simplify_vocabulary", "Replace inflated wording with the ordinary word.",
    order=40, group="vocabulary")
def simplify_vocabulary(text: str, ctx: Context) -> str:
    o = ctx.options
    if o.vocabulary in ("advanced", "academic") or o.formality >= 6:
        return text
    strength = {"simple": 1.0, "casual": 0.95, "natural": 0.85,
                "professional": 0.5, "advanced": 0.0, "academic": 0.0}[o.vocabulary]
    if o.complexity in ("a2", "b1"):
        strength = min(1.0, strength + 0.2)
    if strength <= 0:
        return text
    return _apply_map(text, ctx.lex.get("simplify", {}), ctx, "simplify_vocabulary",
                      "plainer word carries the same meaning", strength)


@op("formalize_vocabulary", "Raise register when high formality is requested.",
    order=41, group="vocabulary")
def formalize_vocabulary(text: str, ctx: Context) -> str:
    o = ctx.options
    if o.formality < 5 and o.vocabulary not in ("advanced", "academic"):
        return text
    return _apply_map(text, ctx.lex.get("formalize", {}), ctx, "formalize_vocabulary",
                      "target register asks for a higher word", 0.6)


@op("soften_boosters", "Take the air out of superlatives.", order=42,
    group="vocabulary")
def soften_boosters(text: str, ctx: Context) -> str:
    if ctx.options.tone in ("persuasive", "enthusiastic") and ctx.options.purpose == "sell":
        probability = 0.35  # sales copy is allowed some enthusiasm
    else:
        probability = 0.8
    return _apply_map(text, ctx.lex.get("boosters_to_soften", {}), ctx,
                      "soften_boosters", "superlative replaced by a plain word",
                      probability)


@op("reduce_repetition", "Vary a content word that repeats too often.",
    order=45, group="vocabulary")
def reduce_repetition(text: str, ctx: Context) -> str:
    """Flag-and-vary: only touches words repeated far above normal density.

    There is no synonym dictionary here on purpose.  Swapping a repeated term
    for a near-synonym is exactly how a rewrite quietly changes meaning, so
    this operation removes *redundant repetitions inside one sentence* rather
    than inventing alternatives.
    """
    from wia.text.segment import sentences as split_sentences
    from wia.text.tokens import words as tokenize

    out = text
    for seg in split_sentences(text):
        toks = tokenize(seg.text)
        if len(toks) < 12:
            continue
        counts: Dict[str, int] = {}
        for t in toks:
            if len(t) > 5 and t not in ctx.lex.get("simplify", {}):
                counts[t] = counts.get(t, 0) + 1
        repeated = [w for w, n in counts.items() if n >= 3]
        for word in repeated:
            ctx.log("reduce_repetition", word, word,
                    f"“{word}” appears {counts[word]} times in one sentence")
    return out
