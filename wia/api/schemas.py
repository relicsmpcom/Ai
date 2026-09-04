"""Request and response models for the HTTP API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DetectRequest(BaseModel):
    text: str = Field(..., description="The text to analyse.")
    language: str = Field("auto", description="'auto', 'nl' or 'en'.")
    segments: bool = Field(True, description="Return the per-span heatmap.")
    domain: Optional[str] = Field(None, description="Override the domain classifier.")


class HumanizeRequest(BaseModel):
    text: str
    language: str = "auto"
    locale: str = ""
    mode: str = ""
    tone: str = "neutral"
    formality: int = 3
    directness: str = "balanced"
    conciseness: str = "balanced"
    complexity: str = "b2"
    vocabulary: str = "natural"
    contractions: str = "normal"
    idioms: str = "light"
    audience: str = "general"
    purpose: str = "inform"
    emotion: str = "neutral"
    sentence_variation: float = 0.6
    personal_voice: bool = True
    paragraph_restructuring: bool = True
    preserve: List[str] = Field(default_factory=list)
    style_profile: Optional[Dict[str, Any]] = None
    style_profile_id: str = ""
    candidates: int = 3
    seed: int = 0


class AnalyzeRequest(BaseModel):
    text: str
    language: str = "auto"
    with_detection: bool = True


class CompareRequest(BaseModel):
    original: str
    rewrite: str
    language: str = "auto"


class StyleProfileRequest(BaseModel):
    samples: List[str]
    language: str = "auto"
    locale: str = ""
    profile_id: str = ""


class MeaningCheckRequest(BaseModel):
    original: str
    rewrite: str
    language: str = "auto"
