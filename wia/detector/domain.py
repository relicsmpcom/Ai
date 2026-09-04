"""Lightweight domain classifier.

Domain matters because the base rate of "sounds generated" varies wildly by
genre: a support macro and a legal clause are formulaic *by design*.  Knowing
the domain lets the platform calibrate per domain instead of punishing whole
genres of legitimate writing.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

DOMAINS = (
    "email", "academic", "marketing", "support", "social", "technical",
    "news", "report", "creative", "general",
)

_CUES: Dict[str, Tuple[Tuple[str, float], ...]] = {
    "email": (
        (r"^\s*(beste|geachte|hallo|hoi|hi|hey|dear)\b", 2.5),
        (r"\b(met vriendelijke groet|mvg|groeten|kind regards|best regards|regards,|cheers,)\b", 2.5),
        (r"\b(bijgevoegd|attached|bijlage|in de bijlage)\b", 1.0),
    ),
    "academic": (
        (r"\(\s*\w+[^)]{0,30}\d{4}\s*\)", 2.0),
        (r"\b(et al\.|ibid\.|hypothes(e|is)|methodologie|methodology|literatuuronderzoek|literature review)\b", 2.0),
        (r"\b(in dit onderzoek|this study|deze scriptie|this paper|we argue|wij stellen)\b", 1.5),
    ),
    "marketing": (
        (r"\b(nu kopen|schrijf je in|sign up|buy now|get started|probeer gratis|free trial|ontdek|discover)\b", 2.0),
        (r"[!]{1,}", 0.4),
        (r"\b(aanbieding|korting|deal|exclusief|exclusive|limited|nieuw!|new!)\b", 1.5),
    ),
    "support": (
        (r"\b(excuses voor het ongemak|sorry for the inconvenience|ticket|klantnummer|order number|ordernummer)\b", 2.5),
        (r"\b(neem contact op|contact us|we hebben uw|we have received your|terugbetaling|refund)\b", 1.5),
    ),
    "social": (
        (r"#\w+", 2.0),
        (r"@\w+", 1.2),
        (r"\b(lol|haha|omg|nou ja|btw|imo|fr fr|ngl)\b", 1.5),
    ),
    "technical": (
        (r"```|\bfunction\b|\bclass\b|\bAPI\b|\bendpoint\b|\bconfig\b|\binstall\b", 1.8),
        (r"\b(versie|version)\s+\d+\.\d+", 1.5),
        (r"^\s*\d+\.\s+\w+", 0.6),
    ),
    "news": (
        (r"\b(volgens|according to)\s+[A-Z]", 1.5),
        (r"\b(woensdag|donderdag|vrijdag|maandag|dinsdag|zaterdag|zondag|monday|tuesday|wednesday|thursday|friday)\b", 0.8),
        (r"\b(zei|said|verklaarde|stated|announced|kondigde aan)\b", 1.2),
    ),
    "report": (
        (r"\b(kwartaal|quarter|Q[1-4]\b|omzet|revenue|KPI|doelstelling|objective)\b", 1.6),
        (r"\b(samenvatting|summary|conclusie|conclusion|aanbeveling|recommendation)\b", 1.2),
        (r"\d+([.,]\d+)?\s*%", 0.8),
    ),
    "creative": (
        (r"\b(hij fluisterde|she whispered|het rook naar|the air smelled|plots|suddenly)\b", 2.0),
        (r"[""«»']{2,}", 0.5),
    ),
}


def classify_domain(text: str) -> Tuple[str, float]:
    """Return ``(domain, confidence)``; ``general`` when nothing stands out."""
    scores = {d: 0.0 for d in DOMAINS}
    lowered = text.lower()
    for domain, cues in _CUES.items():
        for pattern, weight in cues:
            hits = len(re.findall(pattern, lowered, re.MULTILINE))
            if hits:
                scores[domain] += weight * min(3, hits)
    best = max(scores, key=lambda d: scores[d])
    total = sum(scores.values())
    if scores[best] < 2.0:
        return "general", 0.2
    return best, min(1.0, scores[best] / max(1.0, total))
