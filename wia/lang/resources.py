"""Function-word inventories.

Function words carry almost no topic and a lot of authorship signal, which is
why both the language identifier and the stylometric model lean on them.
"""

from __future__ import annotations

from typing import FrozenSet

NL_FUNCTION_WORDS: FrozenSet[str] = frozenset("""
de het een en van in op te dat die is was zijn niet met voor aan er om als maar
dan ook nog wel bij door over naar uit ze hij zij we wij je jij jullie u ik mij
me hem haar hen hun ons onze mijn jouw zijn deze dit dat daar hier waar wie wat
hoe waarom wanneer welke worden wordt werd werden heeft hebben had hadden kan
kunnen kon konden zal zullen zou zouden moet moeten moest mag mogen wil willen
doen doet deed gaan gaat ging komen komt kwam maken maakt maakte al alleen altijd
andere veel meer minder minst weinig zeer erg heel best beter goed nu toen straks
eerst laatst tussen tegen zonder binnen buiten onder boven naast volgens tijdens
sinds ondanks omdat doordat zodat hoewel terwijl indien tenzij want dus echter
bovendien daarnaast daarom immers namelijk trouwens overigens eigenlijk gewoon
misschien waarschijnlijk zeker natuurlijk vooral juist toch even nooit vaak soms
""".split())

EN_FUNCTION_WORDS: FrozenSet[str] = frozenset("""
the a an and or but of in on to for with at by from as is are was were be been
being have has had do does did will would can could shall should may might must
not no nor so than then that this these those there here where when why how who
whom whose which what if unless because since while although though however
therefore thus moreover furthermore additionally also too very much many more
most less least few some any all every each both either neither only just even
still yet again ever never often sometimes always about after before during
between among against without within into onto over under above below through
across around off out up down again further once i me my we us our you your he
him his she her it its they them their
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
_EN_CONTRACTION_STEMS = frozenset(
    "don doesn didn isn aren wasn weren can couldn shouldn wouldn won hasn "
    "haven hadn ain let it's i'm we're they're you're that's there's".split()
)

# Orthographic n-grams: cheap, robust for short inputs where token overlap
# ('de', 'in', 'is') is ambiguous.
_NL_NGRAMS = ("ij", "sch", "aa", "ee ", "oo", "uu", "lijk", "heid", "gen ", "en ", "ge", "kk", "cht")
_EN_NGRAMS = ("th", "the", "ing", "tion", "sh", "wh", "ough", "ly ", "ed ", "ck")


def function_words(language: str) -> FrozenSet[str]:
    return NL_FUNCTION_WORDS if str(language).startswith("nl") else EN_FUNCTION_WORDS
