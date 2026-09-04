"""Transport-independent service layer.

Every endpoint's actual work lives here, in plain Python with no web framework
and no dependencies outside the standard library.  Two callers sit on top:

* :mod:`wia.api.app` — a FastAPI wrapper that validates with pydantic and
  serves it over HTTP;
* the browser build — Pyodide calls :func:`handle` directly, so the whole
  product runs client-side with no server at all.

Keeping the logic here means those two can never drift apart, and it is why a
static host can run the same code the API runs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from wia import __version__

DISCLAIMER = (
    "Authorship estimates are probabilistic and can be wrong. They are not "
    "proof that a person did or did not write a text, and must not be used "
    "alone to accuse anyone."
)


class ServiceError(Exception):
    """A bad request. Carries the status code the HTTP layer should return."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


_detector = None
_humanizer = None
_profiles: Dict[str, Any] = {}


def detector():
    global _detector
    if _detector is None:
        from wia.detector import Detector

        _detector = Detector.load()
    return _detector


def humanizer():
    global _humanizer
    if _humanizer is None:
        from wia.humanizer import Humanizer

        _humanizer = Humanizer()
    return _humanizer


def _require_text(payload: Dict[str, Any], key: str = "text") -> str:
    text = (payload.get(key) or "").strip()
    if not text:
        raise ServiceError(f"{key} is required")
    return text


# ------------------------------------------------------------------ actions --
def health(_: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from wia.features import FEATURES, authorship_feature_names
    from wia.humanizer.modes import MODES
    from wia.humanizer.ops import OPS

    model = detector().model
    return {
        "status": "ok",
        "version": __version__,
        "detector": {
            "trained": bool(model.meta.get("trained")),
            "features_measured": len(FEATURES),
            "features_used_as_evidence": len(authorship_feature_names()),
            "languages": ["nl", "en"],
            "policy": detector().policy.to_dict(),
        },
        "humanizer": {"operations": len(OPS), "modes": len(MODES)},
        "disclaimer": DISCLAIMER,
    }


def detect(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = _require_text(payload)
    result = detector().detect(
        text,
        language=payload.get("language", "auto") or "auto",
        with_segments=bool(payload.get("segments", True)),
        domain=payload.get("domain") or None,
    )
    out = result.to_dict()
    out["disclaimer"] = DISCLAIMER
    return out


def humanize(payload: Dict[str, Any]) -> Dict[str, Any]:
    from wia.humanizer import HumanizeOptions, StyleProfile

    text = _require_text(payload)
    data = dict(payload)
    profile_data = data.pop("style_profile", None)
    profile = None
    if profile_data:
        profile = StyleProfile.from_dict(profile_data)
    else:
        profile_id = data.get("style_profile_id") or ""
        if profile_id and profile_id in _profiles:
            profile = _profiles[profile_id]
    options = HumanizeOptions.from_dict(data)
    return humanizer().humanize(text, options, profile).to_dict()


def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    from wia.analyze import analyze as run

    text = _require_text(payload)
    return run(
        text,
        payload.get("language", "auto") or "auto",
        with_detection=bool(payload.get("with_detection", True)),
    ).to_dict()


def compare(payload: Dict[str, Any]) -> Dict[str, Any]:
    from wia.analyze import compare as run

    original = _require_text(payload, "original")
    rewrite = _require_text(payload, "rewrite")
    return run(original, rewrite, payload.get("language", "auto") or "auto")


def meaning_check(payload: Dict[str, Any]) -> Dict[str, Any]:
    from wia.lang import detect_language
    from wia.meaning.guard import check

    original = _require_text(payload, "original")
    rewrite = _require_text(payload, "rewrite")
    language = payload.get("language", "auto") or "auto"
    if language == "auto":
        language = detect_language(original).language.value
    return check(original, rewrite, language).to_dict()


def style_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    from wia.humanizer import extract_style

    samples: List[str] = [s for s in (payload.get("samples") or []) if s and s.strip()]
    if not samples:
        raise ServiceError("at least one sample is required")
    words = sum(len(s.split()) for s in samples)
    profile = extract_style(
        samples,
        payload.get("language", "auto") or "auto",
        payload.get("locale", "") or "",
        payload.get("profile_id", "") or "",
    )
    _profiles[profile.id] = profile
    return {
        "profile": profile.to_dict(),
        "description": profile.describe(),
        "sample_words": words,
        "advice": (
            "A profile built from under 300 words is a sketch. Paste a few more "
            "pieces of your own writing for a profile worth using."
            if words < 300 else
            "Profile stored for this session only."
        ),
    }


def modes(_: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from wia.humanizer.modes import MODES

    return {"modes": MODES}


def features(_: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """What the detector measures — published, not hidden."""
    from wia.features import FEATURES
    from wia.humanizer.ops import OPS

    return {
        "features": [
            {
                "name": f.name,
                "group": f.group,
                "description": f.doc,
                "tends_toward": f.direction,
                "used_as_authorship_evidence": f.authorship_evidence,
            }
            for f in FEATURES
        ],
        "operations": [
            {"name": o.name, "group": o.group, "description": o.doc}
            for o in sorted(OPS.values(), key=lambda o: o.order)
        ],
    }


ROUTES = {
    "/health": health,
    "/detect": detect,
    "/humanize": humanize,
    "/analyze": analyze,
    "/compare": compare,
    "/meaning-check": meaning_check,
    "/style-profile": style_profile,
    "/modes": modes,
    "/features": features,
}


def handle(path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Dispatch one call. The browser build's entire server, in one function."""
    action = ROUTES.get(path if path.startswith("/") else "/" + path)
    if action is None:
        raise ServiceError(f"unknown endpoint: {path}", status=404)
    return action(payload or {})
