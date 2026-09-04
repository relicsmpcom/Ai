"""HTTP API.

The endpoint surface follows §21 of the roadmap.  Two things it does that a
detection API usually does not:

* every ``/detect`` response carries ``warnings`` and an explicit statement
  that the result is an estimate, in the payload rather than in the docs;
* ``/humanize`` returns the meaning report alongside every candidate, so a
  caller cannot accept a rewrite without also receiving the evidence that it
  says the same thing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from wia import __version__
from wia.analyze import analyze, compare
from wia.api.schemas import (
    AnalyzeRequest,
    CompareRequest,
    DetectRequest,
    HumanizeRequest,
    MeaningCheckRequest,
    StyleProfileRequest,
)
from wia.detector import Detector
from wia.humanizer import HumanizeOptions, Humanizer, StyleProfile, extract_style
from wia.humanizer.modes import MODES
from wia.humanizer.ops import OPS
from wia.features import FEATURES
from wia.meaning.guard import check as meaning_check

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"

DISCLAIMER = (
    "Authorship estimates are probabilistic and can be wrong. They are not "
    "proof that a person did or did not write a text, and must not be used "
    "alone to accuse anyone."
)

app = FastAPI(
    title="WIA — Writing Intelligence Assistant",
    version=__version__,
    description=(
        "Dutch + English authorship estimation, meaning-preserving rewriting "
        "and writing analysis.\n\n" + DISCLAIMER
    ),
)

_detector: Detector | None = None
_humanizer: Humanizer | None = None
_profiles: Dict[str, StyleProfile] = {}


def detector() -> Detector:
    global _detector
    if _detector is None:
        _detector = Detector.load()
    return _detector


def humanizer() -> Humanizer:
    global _humanizer
    if _humanizer is None:
        _humanizer = Humanizer()
    return _humanizer


@app.get("/health")
def health() -> Dict[str, Any]:
    model = detector().model
    return {
        "status": "ok",
        "version": __version__,
        "detector": {
            "trained": bool(model.meta.get("trained")),
            "features": len(FEATURES),
            "languages": ["nl", "en"],
            "policy": detector().policy.to_dict(),
        },
        "humanizer": {"operations": len(OPS), "modes": len(MODES)},
        "disclaimer": DISCLAIMER,
    }


@app.post("/detect")
def detect(req: DetectRequest) -> Dict[str, Any]:
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    result = detector().detect(
        req.text, language=req.language,
        with_segments=req.segments, domain=req.domain,
    )
    payload = result.to_dict()
    payload["disclaimer"] = DISCLAIMER
    return payload


@app.post("/humanize")
def humanize(req: HumanizeRequest) -> Dict[str, Any]:
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    data = req.model_dump()
    profile_data = data.pop("style_profile", None)
    profile_id = data.get("style_profile_id") or ""
    profile = None
    if profile_data:
        profile = StyleProfile.from_dict(profile_data)
    elif profile_id and profile_id in _profiles:
        profile = _profiles[profile_id]
    options = HumanizeOptions.from_dict(data)
    result = humanizer().humanize(req.text, options, profile)
    return result.to_dict()


@app.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest) -> Dict[str, Any]:
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    return analyze(req.text, req.language, with_detection=req.with_detection).to_dict()


@app.post("/compare")
def compare_endpoint(req: CompareRequest) -> Dict[str, Any]:
    if not req.original.strip() or not req.rewrite.strip():
        raise HTTPException(status_code=400, detail="original and rewrite are required")
    return compare(req.original, req.rewrite, req.language)


@app.post("/meaning-check")
def meaning_endpoint(req: MeaningCheckRequest) -> Dict[str, Any]:
    language = req.language
    if language == "auto":
        from wia.lang import detect_language

        language = detect_language(req.original).language.value
    return meaning_check(req.original, req.rewrite, language).to_dict()


@app.post("/style-profile")
def style_profile(req: StyleProfileRequest) -> Dict[str, Any]:
    samples = [s for s in req.samples if s and s.strip()]
    if not samples:
        raise HTTPException(status_code=400, detail="at least one sample is required")
    words = sum(len(s.split()) for s in samples)
    profile = extract_style(samples, req.language, req.locale, req.profile_id)
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


@app.get("/modes")
def modes() -> Dict[str, Any]:
    return {"modes": MODES}


@app.get("/features")
def features() -> Dict[str, Any]:
    """What the detector measures — published, not hidden."""
    return {
        "features": [
            {"name": f.name, "group": f.group, "description": f.doc,
             "tends_toward": f.direction}
            for f in FEATURES
        ],
        "operations": [
            {"name": o.name, "group": o.group, "description": o.doc}
            for o in sorted(OPS.values(), key=lambda o: o.order)
        ],
    }


@app.get("/")
def index() -> Any:
    page = WEB_DIR / "index.html"
    if page.exists():
        return FileResponse(page)
    return JSONResponse({"service": "wia", "version": __version__, "docs": "/docs"})


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
