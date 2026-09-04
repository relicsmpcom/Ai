"""Paragraph restructuring.

Paragraph shape is one of the loudest signals of machine drafting: five
paragraphs of near-identical length, each opening with a connective.  These
operations vary the shape without moving content between topics — splits
happen at sentence boundaries inside a paragraph, merges only between short
neighbours.
"""

from __future__ import annotations

from typing import List

from wia.humanizer.context import Context
from wia.humanizer.ops.registry import op
from wia.text.segment import paragraphs as split_paragraphs, sentences as split_sentences
from wia.text.tokens import mean


@op("restructure_paragraphs", "Vary paragraph length; split walls of text.",
    order=70, group="structure")
def restructure_paragraphs(text: str, ctx: Context) -> str:
    if not ctx.options.paragraph_restructuring:
        return text
    paras = [p.text for p in split_paragraphs(text)]
    if len(paras) < 2:
        return _split_wall(text, ctx)

    sizes = [len(p.split()) for p in paras]
    average = mean(sizes)
    out: List[str] = []
    i = 0
    while i < len(paras):
        current = paras[i]
        size = len(current.split())
        # Merge a stranded one-liner into its neighbour when both are short.
        if (
            size < average * 0.45
            and i + 1 < len(paras)
            and len(paras[i + 1].split()) < average * 0.75
            and ctx.chance(0.5)
        ):
            merged = current.rstrip() + " " + paras[i + 1].lstrip()
            ctx.log("restructure_paragraphs", current[:50], merged[:50],
                    "two short paragraphs read better as one")
            out.append(merged)
            i += 2
            continue
        if size > average * 1.9 and size > 90:
            out.extend(_split_paragraph(current, ctx))
            i += 1
            continue
        out.append(current)
        i += 1
    return "\n\n".join(out)


def _split_paragraph(paragraph: str, ctx: Context) -> List[str]:
    segs = [s.text for s in split_sentences(paragraph)]
    if len(segs) < 4:
        return [paragraph]
    cut = len(segs) // 2
    ctx.log("restructure_paragraphs", paragraph[:50],
            " ".join(segs[:cut])[:50], "paragraph was long enough to be two")
    return [" ".join(segs[:cut]), " ".join(segs[cut:])]


def _split_wall(text: str, ctx: Context) -> str:
    """A single very long paragraph gets a break; readers need somewhere to land."""
    segs = [s.text for s in split_sentences(text)]
    if len(segs) < 7 or len(text.split()) < 130:
        return text
    cut = len(segs) // 2
    ctx.log("restructure_paragraphs", "single paragraph",
            f"{cut} + {len(segs) - cut} sentences", "one long block became two")
    return " ".join(segs[:cut]) + "\n\n" + " ".join(segs[cut:])
