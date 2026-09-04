import pytest

from wia.meaning.anchors import extract_anchors
from wia.meaning.guard import check

ORIGINAL = ("Revenue grew approximately 18% in Q3, according to Maria Sanchez. "
            "We will not ship before 14 March. Order 884-2211 is delayed.")


def test_anchors_normalise_number_formats_across_locales():
    en = extract_anchors("Revenue was 1,420,000 and margin 18.5%.", "en")
    nl = extract_anchors("De omzet was 1.420.000 en de marge 18,5%.", "nl")
    assert "1420000" in en.numbers
    assert "1420000" in nl.numbers
    assert "18.5%" in en.numbers and "18.5%" in nl.numbers


def test_anchors_do_not_shred_reference_numbers():
    a = extract_anchors("Order 884-2211 is delayed.", "en")
    assert "884-2211" in a.identifiers
    assert "884" not in a.numbers and "2211" not in a.numbers


def test_sentence_initial_capitals_are_not_treated_as_names():
    """"It's fine" must not look like a person called It's."""
    a = extract_anchors("It is fine. Two broke. Looked at it.", "en")
    b = extract_anchors("It's fine. Two broke. Looked at it.", "en")
    assert a.entities == b.entities == []


def test_faithful_rewrite_passes():
    rewrite = ("Revenue was up roughly 18% in Q3, Maria Sanchez said. "
               "We won't ship before 14 March. Order 884-2211 is delayed.")
    report = check(ORIGINAL, rewrite, "en")
    assert report.passed
    assert report.score > 0.9


@pytest.mark.parametrize("rewrite,kind", [
    ("Revenue grew more than 25% in Q3, according to Maria Sanchez. We will not ship "
     "before 14 March. Order 884-2211 is delayed.", "number_changed"),
    ("Revenue grew approximately 18% in Q3, according to Maria Sanchez. We will ship "
     "before 14 March. Order 884-2211 is delayed.", "polarity_flipped"),
    ("Revenue definitely grew 18% in Q3, according to Maria Sanchez. We will never ship "
     "before 14 March. Order 884-2211 is delayed.", "certainty_raised"),
    ("Revenue grew approximately 18% in Q3, according to Maria Sanchez at Acme Corporation. "
     "We will not ship before 14 March. Order 884-2211 is delayed.", "entity_added"),
    ("Revenue grew approximately 18% in Q3, according to Maria Sanchez. We will not ship "
     "before 21 April. Order 884-2211 is delayed.", "date_changed"),
])
def test_drift_is_caught_and_blocks(rewrite, kind):
    report = check(ORIGINAL, rewrite, "en")
    assert not report.passed, f"{kind} slipped through"
    assert any(v.kind == kind for v in report.violations), \
        f"expected {kind}, got {[v.kind for v in report.violations]}"


def test_splitting_a_sentence_is_not_a_polarity_flip():
    rewrite = ("Revenue grew approximately 18% in Q3. Maria Sanchez said so. "
               "We will not ship before 14 March. Not yet. Order 884-2211 is delayed.")
    assert check(ORIGINAL, rewrite, "en").passed


def test_quotations_must_survive_untouched():
    original = 'She said "we are not going to rush this" and left.'
    rewrite = 'She said "we will not rush" and left.'
    report = check(original, rewrite, "en")
    assert not report.passed
    assert any(v.kind == "quote_altered" for v in report.violations)


def test_summary_is_human_readable():
    report = check(ORIGINAL, "Revenue grew 90% in Q3.", "en")
    assert report.summary().startswith("Rewrite rejected")
