"""Marker inventories used by the discourse/stylistic features.

These are *families*, never single-word rules.  A feature counts how dense a
whole family is relative to text length; no individual word ever decides an
outcome, because every one of them is also written by humans every day.
"""

from __future__ import annotations

from typing import Dict, FrozenSet

# --- Transitions -----------------------------------------------------------
FORMAL_CONNECTIVES: Dict[str, FrozenSet[str]] = {
    "en": frozenset({
        "furthermore", "moreover", "additionally", "consequently", "therefore",
        "thus", "hence", "nevertheless", "nonetheless", "subsequently",
        "in addition", "in conclusion", "overall", "ultimately", "importantly",
        "notably", "specifically", "in summary", "to summarize", "as a result",
        "in essence", "by contrast", "in contrast", "that being said",
    }),
    "nl": frozenset({
        "bovendien", "daarnaast", "tevens", "derhalve", "bijgevolg", "voorts",
        "desalniettemin", "niettemin", "kortom", "samenvattend", "concluderend",
        "ten slotte", "tot slot", "al met al", "hierdoor", "hiermee", "hierbij",
        "met andere woorden", "in het bijzonder", "ten eerste", "ten tweede",
        "enerzijds", "anderzijds", "daarentegen", "vervolgens",
    }),
}

CASUAL_CONNECTIVES: Dict[str, FrozenSet[str]] = {
    "en": frozenset({
        "still", "that said", "in practice", "meanwhile", "so", "but", "and yet",
        "anyway", "besides", "then again", "on the other hand", "either way",
        "at least", "for what it's worth", "honestly", "actually",
    }),
    "nl": frozenset({
        "toch", "maar", "en toch", "daarom", "dus", "tegelijk", "juist",
        "in de praktijk", "trouwens", "overigens", "eigenlijk", "gewoon",
        "aan de andere kant", "hoe dan ook", "sowieso", "nou ja",
    }),
}

# --- Hedges and boosters ---------------------------------------------------
HEDGES: Dict[str, FrozenSet[str]] = {
    "en": frozenset({
        "maybe", "perhaps", "probably", "possibly", "seems", "seem", "appears",
        "roughly", "about", "around", "somewhat", "fairly", "kind of", "sort of",
        "i think", "i guess", "not sure", "might", "could be", "arguably",
        "to some extent", "in my experience", "as far as i know",
    }),
    "nl": frozenset({
        "misschien", "wellicht", "waarschijnlijk", "vermoedelijk", "lijkt",
        "ongeveer", "rond", "enigszins", "redelijk", "een beetje", "ik denk",
        "volgens mij", "niet zeker", "zou kunnen", "voor zover ik weet",
        "in mijn ervaring", "eerlijk gezegd",
    }),
}

BOOSTERS: Dict[str, FrozenSet[str]] = {
    "en": frozenset({
        "clearly", "obviously", "certainly", "definitely", "undoubtedly",
        "absolutely", "essential", "crucial", "vital", "significant",
        "substantial", "remarkable", "powerful", "robust", "comprehensive",
        "seamless", "cutting-edge", "state-of-the-art", "unparalleled",
        "invaluable", "pivotal", "paramount",
    }),
    "nl": frozenset({
        "duidelijk", "uiteraard", "zeker", "absoluut", "ongetwijfeld",
        "essentieel", "cruciaal", "aanzienlijk", "opmerkelijk", "krachtig",
        "robuust", "uitgebreid", "naadloos", "toonaangevend", "baanbrekend",
        "onmisbaar", "van groot belang",
    }),
}

# --- Template phrasing typical of instruction-tuned generation -------------
# Every one of these is written by humans too; only unusual *density* matters.
TEMPLATE_PHRASES: Dict[str, FrozenSet[str]] = {
    "en": frozenset({
        "it is important to note", "it's important to note", "it is worth noting",
        "plays a crucial role", "plays a vital role", "plays a key role",
        "in today's fast-paced", "in today's digital", "in the ever-evolving",
        "when it comes to", "a wide range of", "a variety of", "delve into",
        "navigate the", "unlock the", "harness the power", "at the end of the day",
        "not only", "but also", "in order to", "serves as a", "is a testament to",
        "the world of", "one of the most", "can be a game changer",
        "let's dive in", "in this article", "as we have seen", "in conclusion",
    }),
    "nl": frozenset({
        "het is belangrijk om", "het is goed om te weten", "speelt een cruciale rol",
        "speelt een belangrijke rol", "in de huidige", "in de snel veranderende",
        "als het gaat om", "een breed scala aan", "een verscheidenheid aan",
        "niet alleen", "maar ook", "om ervoor te zorgen dat", "dient als",
        "de wereld van", "een van de belangrijkste", "in dit artikel",
        "tot slot", "kortom", "in deze blog", "laten we", "duiken we",
    }),
}

CORPORATE_FILLER: Dict[str, FrozenSet[str]] = {
    "en": frozenset({
        "leverage", "utilize", "utilise", "facilitate", "optimize", "optimise",
        "streamline", "synergy", "holistic", "ecosystem", "landscape", "journey",
        "solution", "solutions", "framework", "paradigm", "innovative",
        "empower", "enhance", "enable", "align", "alignment", "stakeholder",
        "deliverable", "actionable", "scalable", "impactful", "bandwidth",
    }),
    "nl": frozenset({
        "benutten", "faciliteren", "optimaliseren", "stroomlijnen", "synergie",
        "holistisch", "ecosysteem", "landschap", "reis", "oplossing",
        "oplossingen", "raamwerk", "innovatief", "versterken", "verbeteren",
        "mogelijk maken", "afstemming", "stakeholder", "schaalbaar",
        "impactvol", "toegevoegde waarde", "proactief",
    }),
}

# --- Personal / experiential markers --------------------------------------
FIRST_PERSON: Dict[str, FrozenSet[str]] = {
    "en": frozenset({"i", "i'm", "i've", "i'd", "i'll", "me", "my", "mine", "myself", "we", "our", "us"}),
    "nl": frozenset({"ik", "mij", "me", "mijn", "wij", "we", "ons", "onze", "mezelf"}),
}

SECOND_PERSON: Dict[str, FrozenSet[str]] = {
    "en": frozenset({"you", "you're", "your", "yours", "yourself"}),
    "nl": frozenset({"je", "jij", "jouw", "jullie", "u", "uw", "jezelf"}),
}

# Subordinating conjunctions: syntactic depth without a parser.
SUBORDINATORS: Dict[str, FrozenSet[str]] = {
    "en": frozenset({
        "because", "although", "though", "while", "whereas", "unless", "until",
        "since", "if", "when", "whenever", "wherever", "after", "before",
        "so that", "even though", "as if", "provided that", "in case",
    }),
    "nl": frozenset({
        "omdat", "doordat", "hoewel", "terwijl", "tenzij", "totdat", "zodat",
        "indien", "als", "wanneer", "voordat", "nadat", "zodra", "aangezien",
        "mits", "opdat", "alsof", "ofschoon",
    }),
}

# Contractions and their expansions (used by the humanizer too).
EN_CONTRACTIONS = {
    "do not": "don't", "does not": "doesn't", "did not": "didn't",
    "is not": "isn't", "are not": "aren't", "was not": "wasn't",
    "were not": "weren't", "have not": "haven't", "has not": "hasn't",
    "had not": "hadn't", "cannot": "can't", "can not": "can't",
    "could not": "couldn't", "would not": "wouldn't", "should not": "shouldn't",
    "will not": "won't", "it is": "it's", "it has": "it's", "that is": "that's",
    "there is": "there's", "what is": "what's", "who is": "who's",
    "let us": "let's", "i am": "I'm", "i have": "I've", "i will": "I'll",
    "i would": "I'd", "you are": "you're", "you have": "you've",
    "you will": "you'll", "we are": "we're", "we have": "we've",
    "we will": "we'll", "they are": "they're", "they have": "they've",
    "they will": "they'll", "he is": "he's", "she is": "she's",
    "there are": "there're", "would have": "would've", "should have": "should've",
    "could have": "could've",
}

# Dutch has no clitic system as regular as English; these are the natural
# informal reductions that native writers actually use in running text.
NL_INFORMAL_FORMS = {
    "het is": "'t is",
    "op het": "op 't",
    "een": "'n",
    "zo een": "zo'n",
    "naar toe": "naartoe",
}


def get(table: Dict[str, FrozenSet[str]], language: str) -> FrozenSet[str]:
    return table.get("nl" if str(language).startswith("nl") else "en", frozenset())
