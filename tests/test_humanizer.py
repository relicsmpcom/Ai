import pytest

from wia.bench.dataset import Dataset
from wia.humanizer import HumanizeOptions, Humanizer, extract_style
from wia.humanizer.critics import naturalness
from wia.humanizer.ops.dutch import deinvert

MACHINE_EN = (
    "In today's fast-paced digital landscape, organizations must leverage innovative solutions to "
    "optimize their workflows. Furthermore, it is important to note that a comprehensive framework "
    "plays a crucial role in driving sustainable growth. Additionally, businesses can streamline "
    "operations, enhance productivity, and empower stakeholders. Moreover, this approach enables "
    "teams to align on shared objectives. In conclusion, embracing these strategies is essential."
)
MACHINE_NL = (
    "In de huidige snel veranderende wereld is het essentieel dat organisaties hun processen "
    "optimaliseren. Bovendien speelt technologie een cruciale rol bij het verbeteren van de "
    "efficiëntie. Daarnaast is het belangrijk om te vermelden dat medewerkers een sleutelrol "
    "vervullen. Kortom, een holistische aanpak is onmisbaar voor duurzaam succes."
)


@pytest.fixture(scope="module")
def humanizer():
    return Humanizer()


def test_three_candidates_are_offered(humanizer):
    result = humanizer.humanize(MACHINE_EN, HumanizeOptions())
    assert [c.label for c in result.candidates] == ["A", "B", "C"]
    assert result.recommended in {"A", "B", "C"}


def test_rewriting_improves_naturalness_of_flat_text(humanizer):
    before = naturalness(MACHINE_EN, "en").score
    best = humanizer.humanize(MACHINE_EN, HumanizeOptions()).best()
    assert best is not None
    assert best.score.naturalness > before


def test_every_accepted_candidate_preserves_meaning(humanizer):
    for text, language in ((MACHINE_EN, "en"), (MACHINE_NL, "nl")):
        result = humanizer.humanize(text, HumanizeOptions(language=language))
        for candidate in result.candidates:
            if candidate.accepted:
                assert candidate.score.meaning_preservation > 85


def test_protected_spans_survive_verbatim(humanizer):
    text = ('The build reads `retry_interval` from config and posts to '
            'https://example.com/hook. She said "do not change this" about order 884-2211. '
            'Furthermore, it is important to note that the framework is comprehensive and robust.')
    result = humanizer.humanize(text, HumanizeOptions(preserve=["RelicSMP"]))
    for candidate in result.candidates:
        assert "retry_interval" in candidate.text
        assert "https://example.com/hook" in candidate.text
        assert "do not change this" in candidate.text
        assert "884-2211" in candidate.text


def test_lowercase_authors_keep_their_lowercase(humanizer):
    text = ("ok so quick update. the deploy went out at 4 and nothing broke, which honestly "
            "surprised me. i'll keep an eye on it tomorrow but i think we're fine.")
    best = humanizer.humanize(text, HumanizeOptions(tone="casual", formality=1)).best()
    assert best.text.split()[0].islower()


def test_dutch_word_order_is_repaired_not_broken(humanizer):
    result = humanizer.humanize(MACHINE_NL, HumanizeOptions(language="nl"))
    for candidate in result.candidates:
        first = candidate.text.split()[0].lower()
        # A Dutch sentence never opens with a bare finite verb unless it is a
        # question — the pipeline must not leave inversion behind.
        assert first not in {"is", "speelt", "zijn", "wordt", "kunnen", "moet"}


@pytest.mark.parametrize("word", ["is het essentieel dat dit klopt.",
                                  "speelt technologie een grote rol hier.",
                                  "wordt de aanvraag snel behandeld."])
def test_deinversion_produces_subject_first_dutch(word):
    out = deinvert(word)
    assert out is not None
    assert out.split()[0].lower() not in {"is", "speelt", "wordt"}


def test_deinversion_declines_when_unsure():
    assert deinvert("is") is None
    assert deinvert("loopt hard") is None


def test_formality_controls_contractions(humanizer):
    text = ("I do not think we can not deliver this. It is going to be tight, but we will manage "
            "if the team does not lose another week to the migration work.")
    casual = humanizer.humanize(text, HumanizeOptions(formality=1, contractions="conversational"))
    formal = humanizer.humanize(text, HumanizeOptions(formality=6, contractions="none"))
    assert "n't" in casual.best().text or "'s" in casual.best().text
    assert "n't" not in formal.best().text


def test_locale_switches_spelling(humanizer):
    text = ("We organize the analysis around three colors and recognize that the program "
            "will not be finalized before the center reopens in the fall.")
    uk = humanizer.humanize(text, HumanizeOptions(locale="en-GB")).best().text
    assert "organise" in uk or "analyse" in uk or "colour" in uk


def test_a_is_gentler_than_c(humanizer):
    result = humanizer.humanize(MACHINE_EN, HumanizeOptions())
    a, c = result.candidates[0], result.candidates[2]
    assert len(a.changes) <= len(c.changes)


def test_style_profile_shapes_the_rewrite(humanizer):
    profile = extract_style([
        "ok so quick update, deploy went fine. i'll watch it tomorrow.",
        "tried it twice. broke twice. third time i just restarted the box and it was fine.",
        "no idea why that worked. moving on.",
    ])
    result = humanizer.humanize(MACHINE_EN, HumanizeOptions(), profile)
    assert result.options["formality"] == profile.formality
    assert result.best().score.style_match > 0


def test_the_disclaimer_is_always_returned(humanizer):
    result = humanizer.humanize(MACHINE_EN, HumanizeOptions())
    assert any("not for" in note or "not" in note for note in result.notes)
    assert "detector" in result.notes[0]


def test_model_backend_output_is_judged_like_any_other(humanizer):
    class Drifting:
        name = "test"

        def rewrite(self, text, brief, language, locale):
            return "Revenue grew more than 40% and Acme Corporation confirmed it."

    result = Humanizer(backend=Drifting()).humanize(
        "Revenue grew approximately 18% in Q3 and the team confirmed it.", HumanizeOptions())
    model_candidate = [c for c in result.candidates if c.label == "D"][0]
    assert not model_candidate.accepted
    assert result.recommended != "D"


def test_whole_corpus_round_trip_preserves_meaning():
    """No document in HumanBench may come back saying something different."""
    humanizer = Humanizer()
    failures = []
    for sample in Dataset.load():
        result = humanizer.humanize(
            sample.text, HumanizeOptions(language=sample.language, locale=sample.locale))
        if result.best() is None:
            failures.append(sample.id)
    assert not failures, f"no acceptable rewrite for: {failures}"


def test_heavy_repetition_is_reported_not_silently_swapped(humanizer):
    """Swapping a repeated term for a near-synonym changes meaning quietly."""
    text = ("The framework is central to the framework strategy. Our framework enables teams to "
            "use the framework effectively. The framework provides support for every framework "
            "requirement across the organization.")
    result = humanizer.humanize(text, HumanizeOptions())
    assert any("framework" in note and "appears" in note for note in result.notes)
    assert "framework" in result.best().text  # reported, not replaced


def test_a_failing_operation_is_reported_rather_than_swallowed():
    from wia.humanizer.context import Context
    from wia.humanizer.ops.registry import OPS, Op, run_ops

    def explode(text, ctx):
        raise ValueError("boom")

    OPS["_test_explode"] = Op("_test_explode", "Test.", explode, 10, "general")
    try:
        ctx = Context(options=HumanizeOptions(), language="en")
        out = run_ops("Some text that survives.", ctx, ["_test_explode"])
        assert out == "Some text that survives."
        assert any("_test_explode" in note for note in ctx.notes)
    finally:
        OPS.pop("_test_explode", None)


def test_article_agreement_survives_a_word_swap(humanizer):
    """Replacing "paramount" with "important" must fix the article too."""
    text = ("A paramount concern is latency across the whole platform. The team treats it as a "
            "crucial issue and reviews it every week without fail.")
    for candidate in humanizer.humanize(text, HumanizeOptions()).candidates:
        assert " a important" not in candidate.text.lower()
        assert "AN " not in candidate.text  # capitalisation, not shouting


def test_a_coordinator_before_an_inverted_dutch_clause_is_repaired(humanizer):
    text = ("Bovendien is het van belang dat u uw aanvraag tijdig indient. Daarnaast dient u de "
            "vereiste documenten mee te sturen. Kortom, een zorgvuldige voorbereiding is cruciaal.")
    for candidate in humanizer.humanize(text, HumanizeOptions(language="nl")).candidates:
        assert "En dient u" not in candidate.text
        assert "En is het" not in candidate.text
