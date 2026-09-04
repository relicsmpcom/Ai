"""Dutch word-order repair.

Dutch is a verb-second language, so a fronted element inverts the subject and
the finite verb:

    Bovendien  speelt  technologie  een rol.
    ^adverbial ^verb   ^subject

Remove or replace that fronted element and the inversion has to be undone, or
the result is not a sentence:

    *Speelt technologie een rol.        → Technologie speelt een rol.
    *En speelt technologie een rol.     → En technologie speelt een rol.

Nothing in the English pipeline needs this, which is exactly why a system that
claims to support Dutch has to be written for Dutch rather than translated
into it.
"""

from __future__ import annotations

import re
from typing import Optional

#: High-frequency finite verbs that can occupy the V2 slot. The list is
#: deliberately conservative: when the opening word is not on it, the sentence
#: is assumed to be subject-first and is left alone.
FINITE_VERBS = frozenset("""
is zijn was waren wordt worden werd werden heeft hebben had hadden kan kunnen
kon konden moet moeten moest moesten zal zullen zou zouden mag mogen wil willen
wilde wilden gaat gaan ging gingen komt komen kwam kwamen staat staan stond
doet doen deed blijft blijven bleef speelt spelen speelde ligt liggen lag geldt
gelden gold biedt bieden bood maakt maken maakte vraagt vragen vroeg betekent
betekenen zorgt zorgen zorgde helpt helpen hielp werkt werken werkte lijkt
lijken leek blijkt blijken bleek hoort horen paste past valt vallen viel telt
groeit groeide daalt daalde stijgt steeg verandert veranderde ontstaat ontstond
bestaat bestaan bestond geeft geven gaf neemt nemen nam ziet zien zag weet
weten wist zegt zeggen zei krijgt krijgen kreeg vindt vinden vond volgt volgen
loopt lopen liep begint beginnen begon eindigt hangt draait richt houdt
""".split())

PRONOUNS = frozenset(
    "het dit dat die deze er hij zij ze we wij ik je jij jullie u men "
    "iedereen niemand iets alles".split())

DETERMINERS = frozenset(
    "de het een deze die dat dit mijn onze uw hun haar zijn geen alle elke "
    "ieder beide sommige veel enkele meerdere ons".split())

#: Words that cannot be (part of) the subject in the V2 slot: prepositions,
#: adverbs and conjunctions.  Anything on this list ends the subject phrase.
NON_SUBJECT = frozenset("""
van in op met voor aan bij uit over door naar tot tussen onder boven binnen
buiten tegen sinds tijdens zonder om na per vanaf volgens ondanks wegens
ook niet altijd vaak nog al weer dan zo echt snel direct even juist toch
wel eens nooit soms hier daar waar en maar want of dus omdat terwijl hoewel
zodat indien als wanneer nadat voordat te
""".split())

_TOKEN_RE = re.compile(r"\S+")


def is_inverted(fragment: str) -> bool:
    """True when the clause opens with a finite verb (i.e. still inverted)."""
    tokens = fragment.split()
    if len(tokens) < 3:
        return False
    first = tokens[0].strip(",.;:!?\"'“”‘’").lower()
    return first in FINITE_VERBS


def deinvert(fragment: str) -> Optional[str]:
    """Undo verb-subject inversion, or return ``None`` if it cannot be done safely.

    Returning ``None`` is a feature: the caller then leaves the sentence alone
    rather than emitting broken Dutch.
    """
    tokens = fragment.split()
    if len(tokens) < 3:
        return None
    verb = tokens[0]
    verb_core = verb.strip(",.;:!?\"'“”‘’").lower()
    if verb_core not in FINITE_VERBS:
        return None

    # Work out where the subject ends.  Pronoun subjects are one token; a
    # noun phrase runs from its determiner up to the first word that cannot be
    # part of it.
    second = tokens[1].strip(",.;:!?\"'“”‘’").lower()
    if second in FINITE_VERBS or second in NON_SUBJECT:
        return None

    if second in PRONOUNS:
        subject_len = 1
    elif second in DETERMINERS:
        subject_len = 1
        for i in range(2, min(len(tokens) - 1, 5)):
            word = tokens[i].strip(",.;:!?\"'“”‘’").lower()
            if word in FINITE_VERBS or word in NON_SUBJECT or word in DETERMINERS:
                break
            subject_len = i
            if subject_len >= 3:
                break
    else:
        subject_len = 1

    subject = tokens[1:1 + subject_len]
    rest = tokens[1 + subject_len:]
    if not subject or not rest:
        return None
    out = " ".join(subject + [verb_core] + rest)
    return out[:1].upper() + out[1:]


def repair_after_fronting_removed(fragment: str) -> Optional[str]:
    """Fix a clause whose fronted element was just deleted."""
    if not is_inverted(fragment):
        stripped = fragment.strip()
        return stripped[:1].upper() + stripped[1:] if stripped else None
    return deinvert(fragment.strip())
