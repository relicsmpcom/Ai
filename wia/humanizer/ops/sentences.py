"""Sentence-level rhythm.

Natural writing varies its sentence length; generated prose settles near one
comfortable width.  These operations move the *distribution* — splitting long
sentences at clause boundaries the language actually offers, merging choppy
runs, and breaking up repeated openings — rather than paraphrasing, which is
where meaning goes to die.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from wia.humanizer.context import Context
from wia.humanizer.ops.registry import op
from wia.text.segment import sentences as split_sentences
from wia.text.tokens import mean, stdev

# Clause boundaries safe to cut at, per language.  The second element is how to
# start the new sentence (empty means "capitalise what follows").
_SPLITS_EN: Tuple[Tuple[str, str], ...] = (
    (r",\s+(?=which\s)", ""),
    (r",\s+and\s+(?=\w+\s+\w+)", ""),
    (r",\s+but\s+(?=\w+\s+\w+)", "But "),
    (r",\s+so\s+(?=\w+\s+\w+)", "So "),
    (r";\s+", ""),
    (r",\s+(?=because\s|although\s|while\s|whereas\s)", ""),
)
_SPLITS_NL: Tuple[Tuple[str, str], ...] = (
    (r",\s+(?=wat\s|hetgeen\s)", ""),
    (r",\s+en\s+(?=\w+\s+\w+)", ""),
    (r",\s+maar\s+(?=\w+\s+\w+)", "Maar "),
    (r",\s+dus\s+(?=\w+\s+\w+)", "Dus "),
    (r";\s+", ""),
    (r",\s+(?=omdat\s|hoewel\s|terwijl\s|waardoor\s)", ""),
)


#: Words that plausibly open an independent clause (a subject or expletive).
_SUBJECT_STARTERS_EN = {
    "i", "we", "you", "he", "she", "it", "they", "there", "this", "that",
    "these", "those", "the", "a", "an", "my", "our", "your", "their", "his",
    "her", "its", "one", "some", "most", "many", "few", "each", "every",
    "no", "nobody", "everyone", "someone", "people", "customers", "users",
    "teams", "companies", "businesses", "organisations", "organizations",
}
_SUBJECT_STARTERS_NL = {
    "ik", "we", "wij", "je", "jij", "jullie", "u", "hij", "zij", "ze", "het",
    "er", "dit", "dat", "deze", "die", "de", "een", "mijn", "onze", "uw",
    "hun", "haar", "zijn", "men", "iedereen", "niemand", "sommige", "veel",
    "klanten", "gebruikers", "teams", "bedrijven", "organisaties",
}


def _looks_like_clause(fragment: str, ctx: Context) -> bool:
    """Cheap check that a fragment can stand as its own sentence."""
    tokens = fragment.split()
    if not tokens:
        return False
    first = tokens[0].strip(",.;:!?\"'“”‘’").lower()
    starters = _SUBJECT_STARTERS_NL if ctx.is_nl else _SUBJECT_STARTERS_EN
    if first in starters:
        return True
    # A capitalised word mid-sentence is usually a name, which can be a subject.
    return tokens[0][:1].isupper() and tokens[0].lower() != tokens[0]


def _target_length(ctx: Context) -> Tuple[int, int]:
    """(long threshold, short threshold) in words, from the requested style."""
    o = ctx.options
    base_long = {"a2": 16, "b1": 20, "b2": 26, "c1": 30, "academic": 34}[o.complexity]
    if o.conciseness in ("shorten", "concise"):
        base_long -= 4
    if o.conciseness in ("detailed", "expanded"):
        base_long += 4
    if ctx.style is not None:
        base_long = int(round(0.5 * base_long + 0.5 * (ctx.style.mean_sentence_length * 1.6)))
    return max(12, base_long), 6


@op("split_long_sentences", "Break over-long sentences at real clause boundaries.",
    order=50, group="rhythm")
def split_long_sentences(text: str, ctx: Context) -> str:
    long_threshold, _ = _target_length(ctx)
    patterns = _SPLITS_NL if ctx.is_nl else _SPLITS_EN
    out: List[str] = []
    for seg in split_sentences(text):
        body = seg.text
        if len(body.split()) <= long_threshold:
            out.append(body)
            continue
        replaced = False
        for pattern, lead in patterns:
            match = re.search(pattern, body)
            if not match:
                continue
            # Only split near the middle; a cut two words in helps nobody.
            position = match.start() / max(1, len(body))
            if not 0.25 <= position <= 0.80:
                continue
            head = body[: match.start()].rstrip(" ,;")
            tail = body[match.end():].lstrip()
            if len(head.split()) < 5 or len(tail.split()) < 5:
                continue
            if not _looks_like_clause(tail, ctx):
                # ", and empower stakeholders" is a shared verb phrase, not a
                # second sentence. Splitting it produces a fragment.
                continue
            tail = (lead + tail) if lead else (tail[:1].upper() + tail[1:])
            new = f"{head}. {tail}"
            ctx.log("split_long_sentences", body[:70], new[:70],
                    f"sentence ran to {len(body.split())} words")
            out.append(new)
            replaced = True
            break
        if not replaced:
            out.append(body)
    return _rejoin(text, out)


@op("merge_short_sentences", "Join a choppy run of very short sentences.",
    order=51, group="rhythm")
def merge_short_sentences(text: str, ctx: Context) -> str:
    _, short_threshold = _target_length(ctx)
    segs = [s.text for s in split_sentences(text)]
    if len(segs) < 3:
        return text
    out: List[str] = []
    i = 0
    joiner = " en " if ctx.is_nl else " and "
    while i < len(segs):
        current = segs[i]
        if (
            i + 1 < len(segs)
            and len(current.split()) <= short_threshold
            and len(segs[i + 1].split()) <= short_threshold
            and current.endswith(".")
            and ctx.chance(0.6)
        ):
            nxt = segs[i + 1]
            merged = current[:-1] + "," + joiner + nxt[:1].lower() + nxt[1:]
            ctx.log("merge_short_sentences", f"{current} {nxt}"[:70], merged[:70],
                    "two very short sentences in a row")
            out.append(merged)
            i += 2
            continue
        out.append(current)
        i += 1
    return _rejoin(text, out)


@op("vary_openings", "Stop consecutive sentences opening with the same word.",
    order=52, group="rhythm")
def vary_openings(text: str, ctx: Context) -> str:
    segs = [s.text for s in split_sentences(text)]
    if len(segs) < 3:
        return text
    out = list(segs)
    for i in range(1, len(out)):
        first_prev = out[i - 1].split()[:1]
        first_cur = out[i].split()[:1]
        if not first_prev or not first_cur:
            continue
        if first_prev[0].lower().strip(",") != first_cur[0].lower().strip(","):
            continue
        moved = _move_adverbial(out[i], ctx)
        if moved and moved != out[i]:
            ctx.log("vary_openings", out[i][:60], moved[:60],
                    "two sentences in a row opened the same way")
            out[i] = moved
    return _rejoin(text, out)


_ADVERBIAL_RE = re.compile(r"^(.*?),\s+(.+)$")


def _move_adverbial(sentence: str, ctx: Context) -> Optional[str]:
    """Move a trailing adverbial to the front, or the reverse."""
    words = sentence.split()
    if len(words) < 8:
        return None
    # Front-load a trailing prepositional phrase: "... in March." -> "In March, ..."
    tail_pattern = (
        r"\s+((?:in|op|sinds|tijdens|na|voor|binnen|vanaf)\s+[^,.;:]{3,30})([.!?]?)$"
        if ctx.is_nl else
        r"\s+((?:in|on|since|during|after|before|within|from)\s+[^,.;:]{3,30})([.!?]?)$"
    )
    m = re.search(tail_pattern, sentence, re.IGNORECASE)
    if m:
        phrase = m.group(1).strip()
        rest = sentence[: m.start()].rstrip(" ,")
        end = m.group(2) or "."
        return f"{phrase[0].upper()}{phrase[1:]}, {rest[0].lower()}{rest[1:]}{end}"
    return None


@op("rhythm_pass", "Push sentence-length variation toward a natural spread.",
    order=55, group="rhythm")
def rhythm_pass(text: str, ctx: Context) -> str:
    """One corrective pass: if the text is still metronomic, break one sentence.

    Deliberately gentle.  Chasing a burstiness target hard produces text that
    is *differently* artificial, which is not an improvement.
    """
    target = 0.30 + 0.35 * ctx.options.sentence_variation
    segs = [s.text for s in split_sentences(text)]
    lengths = [len(s.split()) for s in segs]
    if len(lengths) < 4:
        return text
    m = mean(lengths)
    cv = stdev(lengths) / m if m else 0.0
    if cv >= target:
        return text
    # Split the longest sentence at a real clause boundary nearest its middle.
    # Cutting at an arbitrary comma is how "A, B, and C" becomes a fragment.
    idx = max(range(len(segs)), key=lambda i: lengths[i])
    body = segs[idx]
    patterns = _SPLITS_NL if ctx.is_nl else _SPLITS_EN
    middle = len(body) / 2
    best = None
    for pattern, lead in patterns:
        for match in re.finditer(pattern, body):
            head = body[: match.start()].rstrip(" ,;")
            tail = body[match.end():].lstrip()
            if len(head.split()) < 5 or len(tail.split()) < 5:
                continue
            if not _looks_like_clause(tail, ctx):
                continue
            distance = abs(match.start() - middle)
            if best is None or distance < best[0]:
                best = (distance, head, tail, lead)
    if best is None:
        return text
    _, head, tail, lead = best
    tail = (lead + tail) if lead else (tail[:1].upper() + tail[1:])
    segs[idx] = f"{head}. {tail}"
    ctx.log("rhythm_pass", body[:60], segs[idx][:60],
            f"sentence lengths were too even (variation {cv:.2f} < {target:.2f})")
    return _rejoin(text, segs)


def _rejoin(original: str, segs: List[str]) -> str:
    """Rebuild the text, preserving paragraph breaks from the original."""
    if not segs:
        return original
    paragraphs = original.split("\n\n")
    if len(paragraphs) == 1:
        return " ".join(s.strip() for s in segs if s.strip())
    # Re-distribute sentences across the original paragraph shapes.
    counts = [max(1, len(split_sentences(p))) for p in paragraphs]
    total = sum(counts)
    if total != len(segs):
        scale = len(segs) / total
        counts = [max(1, round(c * scale)) for c in counts]
    out: List[str] = []
    cursor = 0
    for i, count in enumerate(counts):
        chunk = segs[cursor: cursor + count] if i < len(counts) - 1 else segs[cursor:]
        cursor += count
        if chunk:
            out.append(" ".join(s.strip() for s in chunk))
    return "\n\n".join(p for p in out if p)
