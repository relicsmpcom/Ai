import pytest

from wia.features import FEATURES, Doc, extract, feature_names, standardize

AI_LIKE = (
    "In today's fast-paced digital landscape, organizations must leverage innovative solutions. "
    "Furthermore, it is important to note that a comprehensive framework plays a crucial role. "
    "Additionally, businesses can streamline operations, enhance productivity, and empower teams. "
    "Moreover, this approach enables alignment. In conclusion, these strategies are essential."
)
HUMAN_LIKE = (
    "We tried three tools before this one. Two broke on day one; the third lasted a week. "
    "What finally worked was boring: write the steps down, give each one an owner, stop adding "
    "tickets on Fridays. Throughput went up about 20% in a month. Not magic."
)


def test_registry_is_consistent():
    assert len(FEATURES) == len(set(feature_names()))
    for f in FEATURES:
        assert f.doc and f.doc[0].isupper()
        assert f.spread > 0
        assert f.direction in (None, "ai", "human")


def test_every_feature_returns_a_finite_number_on_odd_input():
    for text in ("", "   ", "a", "!!!", "1234", "\n\n\n", "Één zin."):
        values = extract(Doc(text, "nl"))
        assert len(values) == len(FEATURES)
        for name, value in values.items():
            assert isinstance(value, float), name
            assert value == value and abs(value) < 1e9, name


def test_standardisation_is_bounded():
    z = standardize(extract(Doc(AI_LIKE, "en")))
    assert all(-4.0 <= v <= 4.0 for v in z.values())


@pytest.mark.parametrize("name", [
    "template_phrase_rate", "corporate_filler_rate", "formal_connective_rate",
    "length_step_regularity",
])
def test_machine_leaning_features_separate_the_two_samples(name):
    ai = extract(Doc(AI_LIKE, "en"))[name]
    human = extract(Doc(HUMAN_LIKE, "en"))[name]
    assert ai > human, f"{name}: {ai} !> {human}"


@pytest.mark.parametrize("name", ["sentence_len_cv", "hedge_rate", "first_person_rate"])
def test_human_leaning_features_separate_the_two_samples(name):
    ai = extract(Doc(AI_LIKE, "en"))[name]
    human = extract(Doc(HUMAN_LIKE, "en"))[name]
    assert human > ai, f"{name}: {human} !> {ai}"


def test_connectives_are_counted_across_punctuation():
    """A connective followed by a comma still counts — most of them are."""
    with_comma = extract(Doc("Furthermore, this is true. Moreover, that is also true.", "en"))
    assert with_comma["formal_connective_rate"] > 0


def test_features_are_not_merely_length_proxies():
    doubled = Doc(HUMAN_LIKE + " " + HUMAN_LIKE, "en")
    single = Doc(HUMAN_LIKE, "en")
    a, b = extract(single), extract(doubled)
    for name in ("mean_sentence_len", "mean_word_len", "function_word_ratio"):
        assert abs(a[name] - b[name]) < a[name] * 0.35 + 0.5, name


def test_register_is_measured_but_never_votes_on_authorship():
    """Register is genre, not provenance.

    A model allowed to learn "formal ⇒ generated" accuses every non-native
    writer who was taught to write formally, and every lawyer, and every
    government department. These features are reported and feed the formality
    estimate; the detector never sees them.
    """
    from wia.features import authorship_feature_names

    evidence = set(authorship_feature_names())
    assert "formal_register_rate" not in evidence
    assert "casual_register_rate" not in evidence
    assert len(evidence) == len(FEATURES) - 2
    assert "sentence_len_cv" in evidence


def test_formality_estimate_tracks_register_not_word_length():
    from wia.features.derived import estimate_formality

    formal = extract(Doc(
        "Geachte mevrouw De Vries, naar aanleiding van ons gesprek stuur ik u "
        "hierbij de gevraagde stukken. Met vriendelijke groet.", "nl"))
    casual = extract(Doc(
        "Hoi! Even snel: de meeting schuift naar vrijdag. Neem ik gewoon "
        "koffie mee, prima toch?", "nl"))
    assert estimate_formality(formal) >= 5
    assert estimate_formality(casual) <= 2
