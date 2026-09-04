"""The feature battery.

Roughly fifty measurements grouped into rhythm, lexis, syntax, discourse,
orthography and statistics.  They are deliberately *shallow* — no parser, no
embedding model — because shallow features are inspectable, fast, and stable
across the two languages we support.  Depth comes from the model on top of
them, not from any single measurement.
"""

from __future__ import annotations

import re
from collections import Counter

from wia.features import lexicons as LX
from wia.features.doc import Doc
from wia.features.registry import feature
from wia.text.tokens import mean, stdev

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⬀-⯿]"
)
_LIST_LINE_RE = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s+", re.MULTILINE)


# ---------------------------------------------------------------- rhythm ---
@feature("mean_sentence_len", "rhythm",
         "Average sentence length in words.", 17.0, 6.0)
def mean_sentence_len(d: Doc) -> float:
    return mean(d.sentence_lengths)


@feature("sentence_len_cv", "rhythm",
         "Variation in sentence length (burstiness). Human writing swings; "
         "generated prose tends to settle near one comfortable length.",
         0.45, 0.18, direction="human")
def sentence_len_cv(d: Doc) -> float:
    m = mean(d.sentence_lengths)
    return stdev(d.sentence_lengths) / m if m else 0.0


@feature("sentence_len_range", "rhythm",
         "Spread between the shortest and longest sentence, relative to the mean.",
         1.40, 0.60, direction="human")
def sentence_len_range(d: Doc) -> float:
    L = d.sentence_lengths
    m = mean(L)
    return (max(L) - min(L)) / m if L and m else 0.0


@feature("short_sentence_ratio", "rhythm",
         "Share of sentences under nine words.", 0.18, 0.12, direction="human")
def short_sentence_ratio(d: Doc) -> float:
    L = d.sentence_lengths
    return sum(1 for x in L if x < 9) / len(L) if L else 0.0


@feature("long_sentence_ratio", "rhythm",
         "Share of sentences over 28 words.", 0.10, 0.09)
def long_sentence_ratio(d: Doc) -> float:
    L = d.sentence_lengths
    return sum(1 for x in L if x > 28) / len(L) if L else 0.0


@feature("length_step_regularity", "rhythm",
         "How often consecutive sentences are nearly the same length. "
         "Very even stepping is a mild machine signal.", 0.42, 0.18, direction="ai")
def length_step_regularity(d: Doc) -> float:
    L = d.sentence_lengths
    if len(L) < 3:
        return 0.0
    steps = [abs(a - b) for a, b in zip(L, L[1:])]
    return sum(1 for s in steps if s <= 4) / len(steps)


@feature("paragraph_len_cv", "rhythm",
         "Variation in paragraph size.", 0.35, 0.20, direction="human")
def paragraph_len_cv(d: Doc) -> float:
    sizes = [len(p.text.split()) for p in d.paragraphs]
    m = mean(sizes)
    return stdev(sizes) / m if m and len(sizes) > 1 else 0.0


@feature("mean_paragraph_sentences", "rhythm",
         "Average number of sentences per paragraph.", 3.4, 1.6)
def mean_paragraph_sentences(d: Doc) -> float:
    return d.n_sentences / d.n_paragraphs


# ---------------------------------------------------------------- lexis ----
@feature("mattr", "lexis",
         "Moving-average type/token ratio — vocabulary variety, measured in a "
         "way that does not simply fall as the text gets longer.",
         0.74, 0.08, direction="human")
def mattr(d: Doc) -> float:
    w = d.words
    window = 50
    if len(w) < window:
        return len(set(w)) / len(w) if w else 0.0
    ratios = [
        len(set(w[i:i + window])) / window
        for i in range(0, len(w) - window + 1, max(1, window // 5))
    ]
    return mean(ratios)


@feature("hapax_ratio", "lexis",
         "Share of words used exactly once.", 0.62, 0.12, direction="human")
def hapax_ratio(d: Doc) -> float:
    c = d.word_counts
    return sum(1 for v in c.values() if v == 1) / len(c) if c else 0.0


@feature("mean_word_len", "lexis", "Average word length in characters.", 4.8, 0.8)
def mean_word_len(d: Doc) -> float:
    return mean(len(w) for w in d.words)


@feature("long_word_ratio", "lexis",
         "Share of words of eight characters or more.", 0.17, 0.07, direction="ai")
def long_word_ratio(d: Doc) -> float:
    w = d.words
    return sum(1 for x in w if len(x) >= 8) / len(w) if w else 0.0


@feature("function_word_ratio", "lexis",
         "Share of grammatical function words — a classic authorship signal.",
         0.44, 0.08)
def function_word_ratio(d: Doc) -> float:
    w = d.words
    fw = d.function_words
    return sum(1 for x in w if x in fw) / len(w) if w else 0.0


@feature("content_concentration", "lexis",
         "How much of the text is carried by its ten most frequent content words.",
         0.11, 0.05, direction="ai")
def content_concentration(d: Doc) -> float:
    fw = d.function_words
    content = [w for w in d.words if w not in fw and len(w) > 2]
    if not content:
        return 0.0
    top = Counter(content).most_common(10)
    return sum(n for _, n in top) / len(content)


@feature("repeated_bigram_ratio", "lexis",
         "Share of two-word sequences that occur more than once.",
         0.055, 0.04, direction="ai")
def repeated_bigram_ratio(d: Doc) -> float:
    bg = d.bigrams
    if len(bg) < 10:
        return 0.0
    c = Counter(bg)
    return sum(n for n in c.values() if n > 1) / len(bg)


@feature("repeated_trigram_ratio", "lexis",
         "Share of three-word sequences that occur more than once.",
         0.012, 0.02, direction="ai")
def repeated_trigram_ratio(d: Doc) -> float:
    tg = d.trigrams
    if len(tg) < 12:
        return 0.0
    c = Counter(tg)
    return sum(n for n in c.values() if n > 1) / len(tg)


@feature("content_load_variation", "lexis",
         "Sentence-to-sentence swing in information density.",
         0.16, 0.08, direction="human")
def content_load_variation(d: Doc) -> float:
    fw = d.function_words
    loads = [
        sum(1 for w in sw if w not in fw) / len(sw)
        for sw in d.sentence_words if len(sw) >= 4
    ]
    return stdev(loads) if len(loads) > 2 else 0.0


# --------------------------------------------------------------- syntax ----
@feature("commas_per_sentence", "syntax", "Average commas per sentence.", 1.1, 0.7)
def commas_per_sentence(d: Doc) -> float:
    return d.text.count(",") / d.n_sentences


@feature("subordinator_rate", "syntax",
         "Subordinate clause markers per 100 words.", 3.0, 1.6)
def subordinator_rate(d: Doc) -> float:
    return d.rate(d.phrase_count(LX.get(LX.SUBORDINATORS, d.language)))


@feature("opening_diversity", "syntax",
         "How many different words the sentences start with.",
         0.80, 0.14, direction="human")
def opening_diversity(d: Doc) -> float:
    firsts = [sw[0] for sw in d.sentence_words if sw]
    return len(set(firsts)) / len(firsts) if firsts else 0.0


@feature("sentence_initial_connective_ratio", "syntax",
         "Share of sentences opening with a formal connective "
         "(Furthermore…, Bovendien…).", 0.07, 0.08, direction="ai")
def sentence_initial_connective_ratio(d: Doc) -> float:
    conn = LX.get(LX.FORMAL_CONNECTIVES, d.language)
    hits = 0
    for sw in d.sentence_words:
        if not sw:
            continue
        if sw[0] in conn or " ".join(sw[:2]) in conn or " ".join(sw[:3]) in conn:
            hits += 1
    return hits / d.n_sentences


@feature("paragraph_opening_symmetry", "syntax",
         "Whether paragraphs all start the same way structurally.",
         0.20, 0.18, direction="ai")
def paragraph_opening_symmetry(d: Doc) -> float:
    starts = []
    for p in d.paragraphs:
        w = p.text.split()
        if w:
            starts.append(w[0].lower().strip(",.:;"))
    if len(starts) < 3:
        return 0.0
    c = Counter(starts)
    return (len(starts) - len(c)) / len(starts)


@feature("anaphoric_opener_rate", "syntax",
         "Sentences that begin with a bare pointer word (This…, Dit…, Deze…), "
         "the glue generated prose uses to chain claims.",
         0.06, 0.06, direction="ai")
def anaphoric_opener_rate(d: Doc) -> float:
    pointers = {"this", "these", "that", "it"} if d.language == "en" else {
        "dit", "deze", "dat", "die", "hierdoor", "hiermee"}
    firsts = [sw[0] for sw in d.sentence_words if sw]
    return sum(1 for f in firsts if f in pointers) / len(firsts) if firsts else 0.0


@feature("list_marker_ratio", "syntax",
         "Share of lines that are bullets or numbered items.", 0.05, 0.15)
def list_marker_ratio(d: Doc) -> float:
    lines = [l for l in d.text.split("\n") if l.strip()]
    if not lines:
        return 0.0
    return len(_LIST_LINE_RE.findall(d.text)) / len(lines)


# ------------------------------------------------------------ discourse ----
@feature("formal_connective_rate", "discourse",
         "Formal connectives per 100 words.", 0.55, 0.55, direction="ai")
def formal_connective_rate(d: Doc) -> float:
    return d.rate(d.phrase_count(LX.get(LX.FORMAL_CONNECTIVES, d.language)))


@feature("casual_connective_rate", "discourse",
         "Conversational connectives per 100 words.", 0.90, 0.80, direction="human")
def casual_connective_rate(d: Doc) -> float:
    return d.rate(d.phrase_count(LX.get(LX.CASUAL_CONNECTIVES, d.language)))


@feature("hedge_rate", "discourse",
         "Hedging per 100 words — writers who are unsure say so.",
         0.55, 0.55, direction="human")
def hedge_rate(d: Doc) -> float:
    return d.rate(d.phrase_count(LX.get(LX.HEDGES, d.language)))


@feature("booster_rate", "discourse",
         "Intensifiers and superlatives per 100 words.", 0.60, 0.60, direction="ai")
def booster_rate(d: Doc) -> float:
    return d.rate(d.phrase_count(LX.get(LX.BOOSTERS, d.language)))


@feature("template_phrase_rate", "discourse",
         "Density of stock phrasing common in generated text. Humans use these "
         "too — only an unusual concentration counts.", 0.30, 0.45, direction="ai")
def template_phrase_rate(d: Doc) -> float:
    return d.rate(d.phrase_count(LX.get(LX.TEMPLATE_PHRASES, d.language)))


@feature("corporate_filler_rate", "discourse",
         "Abstract business vocabulary per 100 words.", 0.60, 0.70, direction="ai")
def corporate_filler_rate(d: Doc) -> float:
    return d.rate(d.phrase_count(LX.get(LX.CORPORATE_FILLER, d.language)))


@feature("first_person_rate", "discourse",
         "First-person pronouns per 100 words.", 1.6, 1.6, direction="human")
def first_person_rate(d: Doc) -> float:
    fp = LX.get(LX.FIRST_PERSON, d.language)
    return d.rate(sum(1 for w in d.words if w in fp))


@feature("second_person_rate", "discourse",
         "Second-person pronouns per 100 words.", 1.2, 1.4)
def second_person_rate(d: Doc) -> float:
    sp = LX.get(LX.SECOND_PERSON, d.language)
    return d.rate(sum(1 for w in d.words if w in sp))


@feature("formal_register_rate", "discourse",
         "Salutations, closings and officialese per 100 words. Reported and "
         "used to estimate formality, but never used as authorship evidence.",
         0.35, 0.55, direction=None, authorship_evidence=False)
def formal_register_rate(d: Doc) -> float:
    return d.rate(d.phrase_count(LX.get(LX.FORMAL_REGISTER, d.language)))


@feature("casual_register_rate", "discourse",
         "Greetings, fillers and informal shorthand per 100 words. Reported "
         "and used to estimate formality, but never used as authorship "
         "evidence — register is genre, not provenance.",
         0.45, 0.70, direction=None, authorship_evidence=False)
def casual_register_rate(d: Doc) -> float:
    return d.rate(d.phrase_count(LX.get(LX.CASUAL_REGISTER, d.language)))


@feature("tricolon_rate", "discourse",
         "Three-item lists inside a sentence (X, Y and Z) per 100 words.",
         0.35, 0.40, direction="ai")
def tricolon_rate(d: Doc) -> float:
    joiner = r"(?:and|or)" if d.language == "en" else r"(?:en|of)"
    pattern = re.compile(
        rf"\b[\w'’-]+(?:\s+[\w'’-]+){{0,2}},\s+[\w'’-]+(?:\s+[\w'’-]+){{0,2}},?\s+{joiner}\s+[\w'’-]+",
        re.IGNORECASE,
    )
    return d.rate(len(pattern.findall(d.text)))


# ---------------------------------------------------------- orthography ----
@feature("exclamation_rate", "orthography", "Exclamation marks per 100 words.",
         0.25, 0.60, direction="human")
def exclamation_rate(d: Doc) -> float:
    return d.rate(d.text.count("!"))


@feature("question_rate", "orthography", "Question marks per 100 words.", 0.35, 0.60)
def question_rate(d: Doc) -> float:
    return d.rate(d.text.count("?"))


@feature("em_dash_rate", "orthography",
         "Em/en dashes used as punctuation per 100 words.", 0.20, 0.40, direction="ai")
def em_dash_rate(d: Doc) -> float:
    return d.rate(len(re.findall(r"\s[—–]\s|\w—\w", d.text)))


@feature("semicolon_rate", "orthography", "Semicolons per 100 words.",
         0.10, 0.25, direction="ai")
def semicolon_rate(d: Doc) -> float:
    return d.rate(d.text.count(";"))


@feature("colon_rate", "orthography", "Colons per 100 words.", 0.35, 0.45)
def colon_rate(d: Doc) -> float:
    return d.rate(d.text.count(":"))


@feature("ellipsis_rate", "orthography", "Ellipses per 100 words.",
         0.08, 0.25, direction="human")
def ellipsis_rate(d: Doc) -> float:
    return d.rate(len(re.findall(r"\.\.\.|…", d.text)))


@feature("contraction_rate", "orthography",
         "Contracted or reduced forms per 100 words.", 1.0, 1.3, direction="human")
def contraction_rate(d: Doc) -> float:
    if d.language == "nl":
        n = len(re.findall(r"\b(?:'t|'n|'s\s|zo'n|d'r|m'n|z'n|ff|effe|even)\b", d.lowered))
        return d.rate(n)
    return d.rate(len(re.findall(r"\b\w+['’](?:t|s|re|ve|ll|d|m)\b", d.lowered)))


@feature("digit_rate", "orthography",
         "Numbers per 100 words — concrete writing carries numbers.",
         1.2, 1.6, direction="human")
def digit_rate(d: Doc) -> float:
    return d.rate(len(re.findall(r"\d", d.text)) / 2.0)


@feature("proper_noun_rate", "orthography",
         "Capitalised words in mid-sentence position — names, places, products.",
         1.8, 2.0, direction="human")
def proper_noun_rate(d: Doc) -> float:
    hits = 0
    for seg in d.sentences:
        toks = seg.text.split()
        for t in toks[1:]:
            core = t.strip(".,;:!?()\"'“”‘’")
            if core[:1].isupper() and not core.isupper() and len(core) > 1:
                hits += 1
    return d.rate(hits)


@feature("emoji_rate", "orthography", "Emoji per 100 words.", 0.05, 0.40,
         direction="human")
def emoji_rate(d: Doc) -> float:
    return d.rate(len(_EMOJI_RE.findall(d.text)))


@feature("allcaps_rate", "orthography", "Fully capitalised words per 100 words.",
         0.20, 0.50, direction="human")
def allcaps_rate(d: Doc) -> float:
    return d.rate(sum(1 for t in d.surface_tokens if len(t) > 2 and t.isupper()))


@feature("parenthetical_rate", "orthography", "Parenthetical asides per 100 words.",
         0.25, 0.45)
def parenthetical_rate(d: Doc) -> float:
    return d.rate(d.text.count("("))


@feature("informality_noise", "orthography",
         "Small human irregularities: doubled punctuation, spacing slips, "
         "lower-case sentence starts.", 0.15, 0.45, direction="human")
def informality_noise(d: Doc) -> float:
    n = 0
    n += len(re.findall(r"[!?]{2,}", d.text))
    n += len(re.findall(r"\s{2,}\S", d.text))
    n += len(re.findall(r"\w,\w", d.text))
    n += sum(1 for seg in d.sentences if seg.text[:1].islower())
    return d.rate(n)


# ---------------------------------------------------------- statistical ----
@feature("redundancy_gain", "statistical",
         "How much better the text compresses in its real word order than with "
         "the same words shuffled. Repeated phrasing and parallel structure "
         "push this up; it is length- and vocabulary-controlled.",
         0.035, 0.035, direction="ai")
def redundancy_gain(d: Doc) -> float:
    import random
    import zlib

    toks = d.surface_tokens
    if len(toks) < 40:
        return 0.0
    real = zlib.compress(" ".join(toks).encode("utf-8"), 6)
    rng = random.Random(1234)
    shuffled = toks[:]
    rng.shuffle(shuffled)
    baseline = zlib.compress(" ".join(shuffled).encode("utf-8"), 6)
    if not baseline:
        return 0.0
    return max(-0.2, min(0.4, 1.0 - len(real) / len(baseline)))


@feature("adjacent_sentence_overlap", "statistical",
         "Word overlap between neighbouring sentences — restating the same idea.",
         0.10, 0.06, direction="ai")
def adjacent_sentence_overlap(d: Doc) -> float:
    fw = d.function_words
    sets = [
        {w for w in sw if w not in fw and len(w) > 3}
        for sw in d.sentence_words
    ]
    sets = [s for s in sets if s]
    if len(sets) < 2:
        return 0.0
    scores = []
    for a, b in zip(sets, sets[1:]):
        union = a | b
        if union:
            scores.append(len(a & b) / len(union))
    return mean(scores)


@feature("syllables_per_word", "statistical", "Average syllables per word.",
         1.55, 0.25)
def syllables_per_word(d: Doc) -> float:
    return mean(d.syllable_counts, 1.0)


@feature("readability", "statistical",
         "Flesch-style reading ease, rescaled to 0–1 (higher = easier).",
         0.55, 0.18)
def readability(d: Doc) -> float:
    asl = mean(d.sentence_lengths, 15.0)
    asw = mean(d.syllable_counts, 1.5)
    if d.language == "nl":  # Douma's Dutch adaptation
        score = 206.84 - 0.93 * asl - 77.0 * asw
    else:
        score = 206.835 - 1.015 * asl - 84.6 * asw
    return max(0.0, min(1.0, score / 100.0))


@feature("uniform_paragraph_size", "statistical",
         "How close every paragraph is to the same word count.",
         0.55, 0.22, direction="ai")
def uniform_paragraph_size(d: Doc) -> float:
    sizes = [len(p.text.split()) for p in d.paragraphs]
    if len(sizes) < 3:
        return 0.0
    m = mean(sizes)
    if not m:
        return 0.0
    dev = mean(abs(s - m) for s in sizes) / m
    return max(0.0, 1.0 - dev * 2.0)
