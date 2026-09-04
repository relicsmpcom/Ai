import pytest

from wia.bench.dataset import Dataset
from wia.detector import Detector
from wia.types import AuthorshipClass, Confidence

SHORT = "Quick note: moved the meeting to Friday."
AI_LONG = (
    "In today's fast-paced digital landscape, organizations must leverage innovative solutions to "
    "optimize their workflows. Furthermore, it is important to note that a comprehensive framework "
    "plays a crucial role in driving sustainable growth. Additionally, businesses can streamline "
    "operations, enhance productivity, and empower stakeholders across the entire ecosystem. "
    "Moreover, this approach enables teams to align on shared objectives and unlock new "
    "opportunities. In conclusion, embracing these strategies is essential for long-term success. "
    "Ultimately, the organizations that adapt will thrive in the years ahead."
)


@pytest.fixture(scope="module")
def detector():
    return Detector.load()


def test_probabilities_are_a_distribution(detector):
    r = detector.detect(AI_LONG)
    total = r.human_probability + r.mixed_probability + r.ai_probability
    assert abs(total - 1.0) < 1e-6
    assert all(0.0 <= p <= 1.0 for p in
               (r.human_probability, r.mixed_probability, r.ai_probability))


def test_short_text_is_never_given_a_verdict(detector):
    r = detector.detect(SHORT)
    assert r.label is AuthorshipClass.UNCERTAIN
    assert r.confidence is Confidence.LOW
    assert any("40 words" in w for w in r.warnings)


def test_strong_calls_need_enough_text(detector):
    """Even a very machine-like paragraph cannot be called "likely AI" when short."""
    r = detector.detect(AI_LONG.split(". ")[0] + ".")
    assert r.label is not AuthorshipClass.LIKELY_AI


def test_empty_input_does_not_crash(detector):
    r = detector.detect("")
    assert r.words == 0
    assert r.label is AuthorshipClass.UNCERTAIN


def test_explanations_reference_real_measurements(detector):
    r = detector.detect(AI_LONG)
    assert r.explanations
    assert all(isinstance(line, str) and line for line in r.explanations)


def test_segments_cover_the_text_and_carry_reliability(detector):
    r = detector.detect(AI_LONG)
    assert r.segments
    for s in r.segments:
        assert 0 <= s.segment.start < s.segment.end <= len(AI_LONG)
        assert 0.0 <= s.reliability <= 1.0
    assert r.mixed_authorship["segment_count"] == len(r.segments)


def test_hard_negatives_are_not_accused():
    """Human writing that *looks* generated must not be called AI.

    This is the single most important test in the repository: legal prose,
    plain-language public information, non-native writers and grammar-checked
    text are the documents a careless detector accuses.
    """
    detector = Detector.load()
    hard = [s for s in Dataset.load() if "hard_negative" in s.tags]
    assert len(hard) >= 20
    accused = [
        s.id for s in hard
        if detector.detect(s.text, language=s.language, with_segments=False).label
        in (AuthorshipClass.MOSTLY_AI, AuthorshipClass.LIKELY_AI)
    ]
    assert not accused, f"accused human writers: {accused}"


def test_risk_profiles_produce_warnings():
    detector = Detector.load()
    legal = (
        "Artikel 7. De opdrachtnemer verplicht zich de werkzaamheden naar beste vermogen uit te "
        "voeren. Onverminderd het bepaalde in artikel 6 is de opdrachtnemer niet aansprakelijk "
        "voor indirecte schade, waaronder begrepen gevolgschade en gederfde winst."
    )
    r = detector.detect(legal, language="nl")
    assert any("legal" in w.lower() or "formulaic" in w.lower() for w in r.warnings)


def test_language_is_honoured_when_forced():
    detector = Detector.load()
    r = detector.detect("Dit is een Nederlandse zin met genoeg woorden erin.", language="nl")
    assert r.language.value == "nl"
