"""Rewrite lexicons for Dutch and English.

These are data, not rules: the humanizer consults them, weighs them against
the requested tone and formality, and never applies a replacement blindly.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=4)
def load(language: str) -> Dict[str, Any]:
    lang = "nl" if str(language).startswith("nl") else "en"
    return json.loads((_DIR / f"{lang}.json").read_text(encoding="utf-8"))
