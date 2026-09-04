"""Function-word inventories.

Function words carry almost no topic and a lot of authorship signal, which is
why both the language identifier and the stylometric model lean on them.
"""

from __future__ import annotations

from typing import FrozenSet

NL_FUNCTION_WORDS: FrozenSet[str] = frozenset("""
aan al alleen als altijd andere best beter bij binnen boven bovendien buiten
daar daarnaast daarom dan dat de deed deze die dit doen doet door doordat
dus echter een eerst eigenlijk en er erg even gaan gaat gewoon ging goed
haar had hadden hebben heeft heel hem hen het hier hij hoe hoewel hun ik
immers in indien is je jij jouw juist jullie kan komen komt kon konden
kunnen kwam laatst maakt maakte maar mag maken me meer met mij mijn minder
minst misschien moest moet moeten mogen naar naast namelijk natuurlijk niet
nog nooit nu om omdat ondanks onder ons onze ook op over overigens sinds
soms straks te tegen tenzij terwijl tijdens toch toen trouwens tussen u uit
vaak van veel volgens voor vooral waar waarom waarschijnlijk wanneer want
was wat we weinig wel welke werd werden wie wij wil willen worden wordt zal
ze zeer zeker zij zijn zodat zonder zou zouden zullen
""".split())

EN_FUNCTION_WORDS: FrozenSet[str] = frozenset("""
a about above across additionally after again against all also although
always among an and any are around as at be because been before being below
between both but by can could did do does down during each either even ever
every few for from further furthermore had has have he her here him his how
however i if in into is it its just least less many may me might more
moreover most much must my neither never no nor not of off often on once
only onto or our out over shall she should since so some sometimes still
than that the their them then there therefore these they this those though
through thus to too under unless up us very was we were what when where
which while who whom whose why will with within without would yet you your
""".split())

# Words that essentially never appear in the other language and are frequent in
# their own — the strongest single-token evidence available.  Derived by
# subtraction so the shared spelling of "in", "is", "we", "was" never votes.
_SHARED = NL_FUNCTION_WORDS & EN_FUNCTION_WORDS
_NL_MARKERS = frozenset(NL_FUNCTION_WORDS - _SHARED)
_EN_MARKERS = frozenset(
    (EN_FUNCTION_WORDS - _SHARED)
    | {"it", "i", "make", "get", "got", "going", "really", "thing", "things",
       "know", "think", "want", "need", "like", "back", "way", "time"}
)

# Contractions expand to markers so "didn't" / "we're" vote like "did" / "are".
_EN_CONTRACTION_STEMS = frozenset("""
ain aren can couldn didn doesn don hadn hasn haven i'm isn it's let shouldn
that's there's they're wasn we're weren won wouldn you're
""".split())

# Orthographic n-grams: cheap, robust for short inputs where token overlap
# ('de', 'in', 'is') is ambiguous.
_NL_NGRAMS = ("ij", "sch", "aa", "ee ", "oo", "uu", "lijk", "heid", "gen ", "en ", "ge", "kk", "cht")
_EN_NGRAMS = ("th", "the", "ing", "tion", "sh", "wh", "ough", "ly ", "ed ", "ck")


def function_words(language: str) -> FrozenSet[str]:
    return NL_FUNCTION_WORDS if str(language).startswith("nl") else EN_FUNCTION_WORDS
