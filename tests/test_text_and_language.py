import pytest

from wia.lang import detect_language
from wia.text import paragraphs, sentences, windows
from wia.text.tokens import syllables, word_tokens, words


def test_sentence_offsets_map_back_to_the_original():
    text = "Dhr. Jansen kwam langs. Hij zei o.a. dat het goed ging.\n\nTweede alinea!"
    for seg in sentences(text):
        assert text[seg.start:seg.end] == seg.text


@pytest.mark.parametrize("text,expected", [
    ("Dhr. Jansen kwam langs. Hij zei o.a. dat het goed ging.", 2),
    ("Mrs. Smith arrived at 9 a.m. She left at noon.", 2),
    ("Costs rose 3.5% in Q1. That is a lot.", 2),
    ("One sentence only", 1),
])
def test_abbreviations_do_not_split_sentences(text, expected):
    assert len(sentences(text)) == expected


def test_paragraphs_and_windows():
    text = ("Eerste zin hier. Tweede zin hier ook.\n\n"
            "Derde zin in alinea twee. Vierde zin. Vijfde zin erbij.")
    assert len(paragraphs(text)) == 2
    wins = windows(text, target_words=6, stride_words=3)
    assert wins and all(w.end > w.start for w in wins)
    assert wins[0].start == 0


def test_tokenizer_handles_dutch_and_english_forms():
    got = word_tokens("'t Is zo'n coronavirus-maatregel, don't you think? 18,5% in 2024.")
    assert "'t" in got and "zo'n" in got and "don't" in got
    assert "coronavirus-maatregel" in got and "18,5%" in got


def test_words_are_lowercased():
    assert words("The Quick Brown") == ["the", "quick", "brown"]


def test_syllable_estimates_are_plausible():
    assert syllables("the") == 1
    assert syllables("naturalness") >= 3
    assert syllables("") == 0


@pytest.mark.parametrize("text,expected", [
    ("De vergadering is verzet naar donderdag omdat niet iedereen kon.", "nl"),
    ("The meeting has been moved to Thursday because not everyone could make it.", "en"),
    ("Ik heb het gewoon niet gehaald.", "nl"),
    ("I just didn't make it.", "en"),
    ("Wij hebben uw aanvraag ontvangen en beoordelen deze binnen tien werkdagen.", "nl"),
])
def test_language_identification(text, expected):
    assert detect_language(text).language.value == expected


def test_language_declines_to_guess_on_nothing():
    assert detect_language("").language.value == "unknown"
    assert detect_language("").confidence == 0.0
