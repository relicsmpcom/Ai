"""HTTP API.

A thin transport over :mod:`wia.service`, which holds the actual work. The
split exists so the browser build can call exactly the same code with no web
framework in the way — the two can never drift apart.

Two things this API does that a detection API usually does not:

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
from wia.api.schemas import (
    AnalyzeRequest,
    CompareRequest,
    DetectRequest,
    HumanizeRequest,
    MeaningCheckRequest,
    StyleProfileRequest,
)
from wia.service import DISCLAIMER, ServiceError, handle

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="WIA — Writing Intelligence Assistant",
    version=__version__,
    description=(
        "Dutch + English authorship estimation, meaning-preserving rewriting "
        "and writing analysis.\n\n" + DISCLAIMER
    ),
)


def _call(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return handle(path, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc


@app.get("/health")
def health() -> Dict[str, Any]:
    return _call("/health", {})


@app.post("/detect")
def detect(req: DetectRequest) -> Dict[str, Any]:
    return _call("/detect", req.model_dump())


@app.post("/humanize")
def humanize(req: HumanizeRequest) -> Dict[str, Any]:
    return _call("/humanize", req.model_dump())


@app.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest) -> Dict[str, Any]:
    return _call("/analyze", req.model_dump())


@app.post("/compare")
def compare_endpoint(req: CompareRequest) -> Dict[str, Any]:
    return _call("/compare", req.model_dump())


@app.post("/meaning-check")
def meaning_endpoint(req: MeaningCheckRequest) -> Dict[str, Any]:
    return _call("/meaning-check", req.model_dump())


@app.post("/style-profile")
def style_profile(req: StyleProfileRequest) -> Dict[str, Any]:
    return _call("/style-profile", req.model_dump())


@app.get("/modes")
def modes() -> Dict[str, Any]:
    return _call("/modes", {})


@app.get("/features")
def features() -> Dict[str, Any]:
    """What the detector measures — published, not hidden."""
    return _call("/features", {})


@app.get("/")
def index() -> Any:
    page = WEB_DIR / "index.html"
    if page.exists():
        return FileResponse(page)
    return JSONResponse({"service": "wia", "version": __version__, "docs": "/docs"})


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
