"""The rewrite planner.

The planner looks at what is actually wrong with *this* text and picks the
operations that address it.  Running every operation on every input is how a
rewriter turns a perfectly good paragraph into a differently-flawed one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from wia.features import Doc, extract
from wia.humanizer.options import HumanizeOptions

#: Which multi-pass stage each operation group belongs to (roadmap §10.X).
PASSES: Dict[str, int] = {
    "redundancy": 1,
    "transitions": 2,
    "structure": 2,
    "rhythm": 3,
    "vocabulary": 4,
    "register": 4,
    "voice": 4,
    "locale": 5,
    "punctuation": 6,
    "general": 6,
}

PASS_NAMES = {
    1: "meaning-safe trimming",
    2: "structure",
    3: "rhythm",
    4: "style and register",
    5: "locale",
    6: "grammar and consistency",
}

#: Operations that always run: they repair, they never reshape.
ALWAYS = ("repair_dutch_word_order", "tidy_spacing", "fix_articles",
          "fix_sentence_case")


@dataclass
class Plan:
    ops: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    intensity: float = 1.0

    def by_pass(self) -> Dict[int, List[str]]:
        from wia.humanizer.ops import OPS

        out: Dict[int, List[str]] = {}
        for name in self.ops:
            operation = OPS.get(name)
            if not operation:
                continue
            stage = PASSES.get(operation.group, 6)
            out.setdefault(stage, []).append(name)
        return dict(sorted(out.items()))

    def to_dict(self) -> dict:
        return {
            "operations": self.ops,
            "findings": self.findings,
            "intensity": round(self.intensity, 2),
            "passes": {
                f"{k}. {PASS_NAMES[k]}": v for k, v in self.by_pass().items()
            },
        }


def build_plan(text: str, options: HumanizeOptions, language: str = "en") -> Plan:
    doc = Doc(text, language)
    f = extract(doc)
    plan = Plan()
    ops: List[str] = []
    findings: List[str] = []

    def want(name: str, finding: str = "") -> None:
        if name not in ops:
            ops.append(name)
        if finding and finding not in findings:
            findings.append(finding)

    # --- what is actually wrong -------------------------------------------
    if f["template_phrase_rate"] > 0.35:
        want("drop_stock_phrases", "stock phrasing that carries no information")
    if f["formal_connective_rate"] > 0.6 or f["sentence_initial_connective_ratio"] > 0.10:
        want("vary_transitions", "mechanical connectives doing the work of argument")
        want("limit_transition_repeats")
    if f["corporate_filler_rate"] > 0.7:
        want("simplify_vocabulary", "abstract business vocabulary")
    if f["booster_rate"] > 0.8:
        want("soften_boosters", "superlatives inflating ordinary claims")
    if f["adjacent_sentence_overlap"] > 0.18:
        want("drop_restated_sentences", "neighbouring sentences restating each other")
    if f["sentence_len_cv"] < 0.42 and doc.n_sentences >= 4:
        want("split_long_sentences", "sentence lengths are unusually even")
        want("merge_short_sentences")
        want("rhythm_pass")
    if f["long_sentence_ratio"] > 0.25:
        want("split_long_sentences", "several sentences run long")
    if f["short_sentence_ratio"] > 0.55 and doc.n_sentences >= 5:
        want("merge_short_sentences", "the rhythm is choppy")
    if f["opening_diversity"] < 0.75 and doc.n_sentences >= 4:
        want("vary_openings", "sentences keep opening the same way")
    if f["uniform_paragraph_size"] > 0.55 or f["paragraph_len_cv"] < 0.18:
        want("restructure_paragraphs", "paragraphs are all the same size")
    if doc.n_words > 130 and doc.n_paragraphs == 1:
        want("restructure_paragraphs", "one long block with nowhere for the eye to rest")
    if f["em_dash_rate"] > 0.35:
        want("normalize_dashes", "display dashes used as general punctuation")
    if f["semicolon_rate"] > 0.25:
        want("reduce_semicolons")
    if f["repeated_bigram_ratio"] > 0.09:
        want("flag_repetition", "repeated phrasing")
    if f["formal_connective_rate"] > 0.3:
        want("drop_empty_openers")

    # --- what the user asked for ------------------------------------------
    if options.contractions != "none":
        want("apply_contractions")
    if options.formality >= 5:
        want("expand_contractions")
        want("formalize_vocabulary")
    if options.vocabulary in ("simple", "casual") or options.complexity in ("a2", "b1"):
        want("simplify_vocabulary")
    if options.directness != "balanced":
        want("adjust_directness")
        want("soften_imperatives")
    if language.startswith("nl"):
        want("set_register")
    if options.locale:
        want("apply_locale")
    if options.conciseness in ("shorten", "concise"):
        want("drop_stock_phrases")
        want("trim_summary_close")
        want("split_long_sentences")
    if options.sentence_variation >= 0.75:
        want("split_long_sentences")
        want("vary_openings")
        want("rhythm_pass")

    ops.extend(name for name in ALWAYS if name not in ops)
    plan.ops = ops
    plan.findings = findings
    return plan
