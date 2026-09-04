"""WIA — Writing Intelligence Assistant.

A Dutch + English writing-authenticity platform:

* ``wia.detector``  — calibrated, probabilistic authorship estimation
* ``wia.humanizer`` — meaning-preserving naturalness rewriting
* ``wia.analyze``   — writing & style analysis
* ``wia.bench``     — HumanBench-NL/EN evaluation harness

The public promise of this package is deliberately narrow: it estimates how a
text was *likely* produced and it improves writing.  It never claims proof of
authorship and it is not built to defeat integrity systems.
"""

__version__ = "0.1.0"

from wia.types import (  # noqa: F401
    AuthorshipClass,
    Confidence,
    DetectionResult,
    Language,
    Locale,
    Segment,
    SegmentResult,
)

__all__ = [
    "__version__",
    "AuthorshipClass",
    "Confidence",
    "DetectionResult",
    "Language",
    "Locale",
    "Segment",
    "SegmentResult",
]
