"""Rewrite operations.

Each operation is small, independent, and reversible in the sense that it
never invents content: it re-expresses what is already there.  The planner
decides which ones run and in what order; the critics decide whether the
result was an improvement.
"""

from wia.humanizer.ops.registry import OPS, Op, get_op, op, run_ops  # noqa: F401

# Importing the modules registers their operations.
from wia.humanizer.ops import (  # noqa: F401,E402
    contractions,
    locale,
    paragraphs,
    punctuation,
    redundancy,
    sentences,
    transitions,
    voice,
    vocabulary,
)

__all__ = ["OPS", "Op", "get_op", "op", "run_ops"]
