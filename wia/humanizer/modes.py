"""Named humanizer modes (roadmap §11).

A mode is nothing more than a named bundle of option defaults.  Users can
still override any single control afterwards — modes are a starting point, not
a cage.
"""

from __future__ import annotations

from typing import Any, Dict

from wia.humanizer.options import HumanizeOptions

MODES: Dict[str, Dict[str, Any]] = {
    # --- Dutch ------------------------------------------------------------
    "natuurlijk_nederlands": {
        "language": "nl", "locale": "nl-NL", "tone": "neutral", "formality": 3,
        "vocabulary": "natural", "contractions": "light", "sentence_variation": 0.7,
    },
    "zakelijk_nederlands": {
        "language": "nl", "locale": "nl-NL", "tone": "professional", "formality": 4,
        "vocabulary": "professional", "contractions": "none",
        "sentence_variation": 0.5, "directness": "balanced",
    },
    "informeel_nederlands": {
        "language": "nl", "locale": "nl-NL", "tone": "casual", "formality": 2,
        "vocabulary": "casual", "contractions": "conversational",
        "sentence_variation": 0.85, "idioms": "normal",
    },
    "academisch_nederlands": {
        "language": "nl", "locale": "nl-NL", "tone": "academic", "formality": 6,
        "vocabulary": "academic", "contractions": "none", "complexity": "academic",
        "sentence_variation": 0.4, "personal_voice": False,
    },
    "studentenstijl": {
        "language": "nl", "locale": "nl-NL", "tone": "neutral", "formality": 3,
        "vocabulary": "natural", "complexity": "b2", "contractions": "light",
        "sentence_variation": 0.75,
    },
    "professionele_email": {
        "language": "nl", "locale": "nl-NL", "tone": "professional", "formality": 4,
        "conciseness": "concise", "directness": "direct", "purpose": "request",
        "audience": "colleague", "sentence_variation": 0.55,
    },
    "nl_marketing": {
        "language": "nl", "locale": "nl-NL", "tone": "persuasive", "formality": 2,
        "vocabulary": "natural", "conciseness": "concise", "purpose": "sell",
        "sentence_variation": 0.9, "idioms": "normal",
    },
    "nl_social": {
        "language": "nl", "locale": "nl-NL", "tone": "casual", "formality": 1,
        "conciseness": "shorten", "contractions": "conversational",
        "sentence_variation": 0.95, "audience": "social",
    },
    "klantenservice": {
        "language": "nl", "locale": "nl-NL", "tone": "empathetic", "formality": 3,
        "directness": "diplomatic", "purpose": "apologize", "audience": "customer",
        "conciseness": "concise", "sentence_variation": 0.6,
    },
    "vlaams": {
        "language": "nl", "locale": "nl-BE", "tone": "friendly", "formality": 3,
        "vocabulary": "natural", "sentence_variation": 0.7,
    },
    "nederlands_nederland": {
        "language": "nl", "locale": "nl-NL", "tone": "neutral", "formality": 3,
    },
    # --- English ----------------------------------------------------------
    "natural_english": {
        "language": "en", "locale": "en-INT", "tone": "neutral", "formality": 3,
        "vocabulary": "natural", "contractions": "normal", "sentence_variation": 0.7,
    },
    "professional_english": {
        "language": "en", "locale": "en-INT", "tone": "professional", "formality": 4,
        "vocabulary": "professional", "contractions": "light",
        "sentence_variation": 0.55,
    },
    "academic_english": {
        "language": "en", "locale": "en-GB", "tone": "academic", "formality": 6,
        "vocabulary": "academic", "contractions": "none", "complexity": "academic",
        "sentence_variation": 0.4, "personal_voice": False,
    },
    "student_writing": {
        "language": "en", "locale": "en-GB", "tone": "neutral", "formality": 3,
        "complexity": "b2", "contractions": "light", "sentence_variation": 0.75,
    },
    "email": {
        "language": "en", "locale": "en-INT", "tone": "professional", "formality": 3,
        "conciseness": "concise", "directness": "direct", "purpose": "request",
        "audience": "colleague", "sentence_variation": 0.6,
    },
    "en_marketing": {
        "language": "en", "locale": "en-US", "tone": "persuasive", "formality": 2,
        "conciseness": "concise", "purpose": "sell", "sentence_variation": 0.9,
        "idioms": "normal",
    },
    "en_social": {
        "language": "en", "locale": "en-US", "tone": "casual", "formality": 1,
        "conciseness": "shorten", "contractions": "conversational",
        "sentence_variation": 0.95, "audience": "social",
    },
    "customer_support": {
        "language": "en", "locale": "en-INT", "tone": "empathetic", "formality": 3,
        "directness": "diplomatic", "purpose": "apologize", "audience": "customer",
        "conciseness": "concise", "sentence_variation": 0.6,
    },
    "us_english": {"language": "en", "locale": "en-US"},
    "uk_english": {"language": "en", "locale": "en-GB"},
    "international_english": {"language": "en", "locale": "en-INT"},
    # --- Style DNA presets (roadmap §10.W) --------------------------------
    "sound_like_me": {"sentence_variation": 0.7},
    "like_me_but_clearer": {"conciseness": "concise", "complexity": "b2",
                            "vocabulary": "natural"},
    "like_me_but_professional": {"formality": 4, "tone": "professional",
                                 "vocabulary": "professional"},
    "like_me_but_shorter": {"conciseness": "shorten"},
    "like_me_but_warmer": {"tone": "warm", "emotion": "warm"},
}

ALIASES = {
    "natural": "natural_english", "professional": "professional_english",
    "academic": "academic_english", "casual": "en_social",
    "concise": "email", "marketing": "en_marketing",
    "zakelijk": "zakelijk_nederlands", "informeel": "informeel_nederlands",
    "natuurlijk": "natuurlijk_nederlands", "academisch": "academisch_nederlands",
}


def resolve(name: str) -> str:
    key = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
    return ALIASES.get(key, key)


def apply_mode(options: HumanizeOptions, name: str) -> HumanizeOptions:
    """Return options with the mode's defaults applied under explicit values."""
    key = resolve(name)
    preset = MODES.get(key)
    if not preset:
        return options
    data = options.to_dict()
    defaults = HumanizeOptions().to_dict()
    for field_name, value in preset.items():
        # An explicitly-set option always wins over the mode's default.
        if data.get(field_name) == defaults.get(field_name):
            data[field_name] = value
    data["mode"] = key
    return HumanizeOptions(**data)


def list_modes() -> Dict[str, Dict[str, Any]]:
    return dict(MODES)
