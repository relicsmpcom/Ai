"""Optional model-backed rewriting.

The rule engine is the default because it is deterministic, offline, fast and
inspectable.  A language model is better at some things it cannot do — real
paraphrase, genuine restructuring — so this module lets one be plugged in as
*another candidate generator*.

The important part is what does not change when you plug one in: the model's
output goes through exactly the same meaning guard and the same critics as the
rule-based candidates, and is rejected on exactly the same terms.  A model that
changes a number loses, however nicely it writes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol

DEFAULT_MODEL = "claude-opus-5"

#: Constraints the model is held to. They restate the product's promises, and
#: the meaning guard enforces them regardless of whether the model complies.
SYSTEM_PROMPT = """You rewrite text so it reads naturally, in the writer's own voice.

Hard rules, in priority order:

1. Never change what the text says. Every number, date, name, quotation,
   reference, URL and identifier must survive exactly. Never add a fact,
   an example, a statistic or a personal experience that is not already there.
2. Never flip a claim between positive and negative, and never make the writer
   sound more certain than they were. "may" does not become "will"; "roughly
   18%" does not become "over 20%".
3. Keep the writer's voice. You are removing flatness, not installing your own
   style. If they write short sentences, keep them short. If they write in
   lower case, keep it.
4. Vary sentence length and openings; cut stock phrases that carry no
   information; prefer the ordinary word over the inflated one.
5. Do not deliberately introduce errors, fake typos, or random slang.

You are not trying to change any detector's opinion of the text, and nothing
about detection should influence your choices.

Reply with the rewritten text and nothing else — no preamble, no explanation,
no markdown fences."""


class RewriteBackend(Protocol):
    """Anything that can propose a rewrite."""

    name: str

    def rewrite(self, text: str, brief: str, language: str, locale: str) -> Optional[str]:
        ...


@dataclass
class NullBackend:
    """The default: no model, no network, no surprises."""

    name: str = "none"

    def rewrite(self, text: str, brief: str, language: str, locale: str) -> Optional[str]:
        return None


class AnthropicBackend:
    """Rewrites through the Claude API.

    Constructed lazily so that ``wia`` keeps working — and keeps its tests
    passing — with no ``anthropic`` package and no API key present.
    """

    def __init__(self, model: str = DEFAULT_MODEL, client: Any = None,
                 max_output_tokens: int = 16000) -> None:
        self.name = f"anthropic:{model}"
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._client = client

    @property
    def available(self) -> bool:
        if self._client is not None:
            return True
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def rewrite(self, text: str, brief: str, language: str, locale: str) -> Optional[str]:
        try:
            import anthropic
        except ImportError:
            return None

        client = self._get_client()
        # Output is roughly the length of the input; leave generous headroom
        # but never ask for more than the configured ceiling.
        budget = max(1024, min(self.max_output_tokens, len(text.split()) * 4 + 512))
        language_name = "Dutch" if str(language).startswith("nl") else "English"
        prompt = (
            f"Rewrite the following {language_name} text ({locale}).\n\n"
            f"What the rewrite should do:\n{brief}\n\n"
            f"---\n{text}\n---"
        )
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=budget,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.BadRequestError:
            return None
        except anthropic.AuthenticationError:
            return None
        except anthropic.RateLimitError:
            return None
        except anthropic.APIStatusError:
            return None
        except anthropic.APIConnectionError:
            return None

        if getattr(response, "stop_reason", None) == "refusal":
            return None
        parts = [b.text for b in response.content if getattr(b, "type", "") == "text"]
        out = "\n".join(parts).strip()
        return out or None


def build_brief(options: Any, plan: Any, profile: Any = None) -> str:
    """Turn the requested controls into instructions a model can follow."""
    lines: List[str] = []
    if getattr(plan, "findings", None):
        lines.append("Problems found in the text: " + "; ".join(plan.findings) + ".")
    lines.append(
        f"Target register: {options.formality_label} (level {options.formality}/6), "
        f"tone {options.tone}, directness {options.directness}, "
        f"length {options.conciseness}, reading level {options.complexity}."
    )
    lines.append(
        f"Audience: {options.audience}. Purpose: {options.purpose}. "
        f"Emotional colour: {options.emotion}."
    )
    if options.contractions == "none":
        lines.append("Do not use contracted forms.")
    elif options.contractions == "conversational":
        lines.append("Contract freely, as in speech.")
    if options.sentence_variation >= 0.75:
        lines.append("Vary sentence length noticeably.")
    if options.preserve:
        lines.append("Keep these exactly as written: " + "; ".join(options.preserve) + ".")
    if profile is not None:
        lines.append("Match this writer's habits: " + " ".join(profile.describe()))
    return "\n".join(f"- {line}" for line in lines)


def resolve_backend(name: str = "", model: str = DEFAULT_MODEL) -> RewriteBackend:
    """Pick a backend by name; fall back to the rule engine when unavailable."""
    if name in ("", "none", "rules"):
        return NullBackend()
    if name in ("anthropic", "claude"):
        backend = AnthropicBackend(model=model)
        return backend if backend.available else NullBackend()
    return NullBackend()
