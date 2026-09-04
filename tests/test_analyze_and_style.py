
from wia.analyze import analyze, compare
from wia.humanizer import extract_style, style_match

FLAT = (
    "The system processes requests in order. The system validates each request first. "
    "The system then stores the result. The system returns a confirmation to the caller. "
    "The system logs every step for auditing. The system retries once on failure. "
    "The system reports the outcome to the dashboard every night."
)
CASUAL = [
    "ok so quick update — the deploy went out at 4 and nothing broke, which surprised me.",
    "hey can you look at that ticket? the weird caching thing from tuesday. no rush :)",
    "tried three things and only the boring one worked. writing the steps down. that's it.",
]


def test_analysis_covers_the_basics():
    report = analyze(FLAT, "en")
    assert report.words > 40
    assert report.sentences == 7
    assert 0 <= report.readability["score"] <= 100
    assert report.rhythm["lengths"]
    assert report.style["profile"]["language"] == "en"


def test_analysis_notices_flat_rhythm_and_repeated_openings():
    kinds = {issue.kind for issue in analyze(FLAT, "en").issues}
    assert "flat_rhythm" in kinds
    assert "repeated_openings" in kinds


def test_analysis_notices_dutch_register_mixing():
    text = ("Je kunt het formulier hier invullen. U ontvangt daarna een bevestiging. "
            "Als je vragen hebt kun je ons bellen. Wij helpen u graag verder met uw aanvraag.")
    kinds = {issue.kind for issue in analyze(text, "nl").issues}
    assert "register_mix" in kinds


def test_analysis_notices_mixed_spelling():
    text = ("We organize the work and analyse the results. We recognise the risk and organize "
            "a review. The team will analyze it again and organise the follow-up.")
    kinds = {issue.kind for issue in analyze(text, "en").issues}
    assert "spelling_mix" in kinds


def test_short_text_skips_detection():
    assert analyze("Too short.", "en").detection is None


def test_compare_reports_meaning_and_deltas():
    result = compare(
        "Furthermore, the team utilized innovative solutions to optimize their workflows.",
        "The team also used new tools to speed up their work.",
    )
    assert result["meaning"]["passed"] is True
    assert result["deltas"]["naturalness"] > 0


def test_style_profile_describes_a_casual_writer():
    profile = extract_style(CASUAL)
    assert profile.formality <= 2
    assert profile.n_samples == 3
    assert profile.mean_sentence_length > 0
    assert any("contract" in line.lower() or "first person" in line.lower()
               for line in profile.describe())


def test_style_match_prefers_the_writers_own_voice():
    profile = extract_style(CASUAL)
    own = style_match("quick one — pushed the fix, looks fine, i'll check again tomorrow.", profile)
    other = style_match(
        "Geachte heer, hierbij bevestig ik de ontvangst van uw aanvraag conform artikel 7 "
        "van de algemene voorwaarden, welke van toepassing zijn op deze overeenkomst.", profile)
    assert own > other


def test_empty_profile_does_not_crash():
    profile = extract_style([])
    assert profile.id == "empty"
    assert profile.describe()
