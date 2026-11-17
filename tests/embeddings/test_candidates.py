"""Cheap target-sentence filtering before model loading or embedding inference."""

import pytest

from dataset.embeddings import target_matching

KEYWORDS = {
    "judgment": ["zasądz"],
    "request": ["żąda"],
    "shared": ["przyzna", "odszkod"],
    "prior_payment": ["wypłac"],
    "procedural_costs": ["koszt"],
    "mixed": ["utrzyma"],
    "other_payments": ["odset", "rent", "grzywn"],
}


@pytest.mark.parametrize(
    "unit",
    [
        "PLN",
        "zł",
        "złoty",
        "złotego",
        "złotemu",
        "złotym",
        "złote",
        "złotych",
        "złotymi",
        "złotówka",
        "złotówki",
        "złotówkę",
        "złotówką",
        "złotówko",
        "złotówek",
        "złotówkom",
        "złotówkami",
        "złotówkach",
        "złotówce",
    ],
)
def test_currency_inflections_are_candidates_and_parse_as_pln(unit):
    """Recognize Polish currency inflections in matching and monetary parsing.

    args:
        unit: Currency abbreviation or inflected Polish name.

    returns:
        None.
    """
    from dataset.extraction.source.text import CURRENCY, MONEY, amount_in_pln

    text = f"Zasądza 100 {unit}."
    assert len(target_matching.candidate_sentences(text, KEYWORDS)) == 1
    assert CURRENCY.fullmatch(unit)
    assert amount_in_pln(MONEY.search(text)) == "100"


@pytest.mark.parametrize(
    ("text", "eligible"),
    [
        ("ZASĄDZA kwotę 20000 zł.", True),
        ("Zasądzono 200 złotych.", True),
        ("Powódka żądała 500 PLN.", True),
        ("Przyznano 100 (sto) zł.", True),
        ("Odszkodowanie wynosi 1,5 tys. zł.", True),
        ("Powód doznał obrażeń.", False),
        ("Zasądza świadczenie bez podania kwoty.", False),
        ("Zasądza świadczenie w złotych.", False),
        ("Zasądza 20000.", False),
        ("Zasądza 200 EUR.", False),
        ("Rachunek opiewa na 300 zł.", False),
        ("Niezasądzona kwota to 100 zł.", False),
        ("Zasądza świadczenie. Rachunek opiewa na 100 zł.", False),
    ],
)
def test_money_currency_and_core_word_must_cooccur_in_one_sentence(text, eligible):
    """
    Require all candidate cues in the same source sentence before embedding.

    args:
        text: Judgment excerpt.
        eligible: Whether a sentence meets all requirements.

    returns:
        None.
    """
    assert bool(target_matching.candidate_sentences(text, KEYWORDS)) is eligible


def test_candidate_filter_preserves_offsets_and_does_not_match_word_interiors():
    """
    Keep exact source positions after rejecting unrelated paragraphs and sentences.

    args:
        None.

    returns:
        None.
    """
    text = "Nagłówek.\nPowód doznał obrażeń. Zasądza 100 zł. Inny opis.\nPowód żąda 200 zł."
    rows = target_matching.candidate_sentences(text, KEYWORDS)
    assert [row["text"] for row in rows] == ["Zasądza 100 zł.", "Powód żąda 200 zł."]
    assert all(text[row["start"] : row["end"]] == row["text"] for row in rows)




def test_prefix_keeps_earlier_keyword_and_leaves_feature_sentences_intact():
    """Retain an earlier role cue while leaving feature sentence splitting unchanged.

    args:
        None

    returns:
        None.
    """
    from dataset.extraction.source.text import sentence_fragments

    text = "Zasądza świadczenie, rachunek opiewa na 100 zł."
    (candidate,) = target_matching.candidate_sentences(text, KEYWORDS)
    assert candidate["text"] == text
    assert candidate["classes"] == ("judgment",)
    assert [row["text"] for row in sentence_fragments({"text": text, "start": 0})] == [
        text
    ]


def test_empty_text_does_not_load_the_embedding_model(monkeypatch):
    """
    Return missing matches without loading weights when there is no text to scan.

    args:
        monkeypatch: Scoped model-factory replacement.

    returns:
        None.
    """
    monkeypatch.setattr(
        target_matching,
        "cached_matcher",
        lambda *args: pytest.fail("Model must not load"),
    )
    config = {"embedding": {"candidate_keywords": KEYWORDS}}
    assert target_matching.match_targets(
        " \n ", config
    ) == dict.fromkeys(target_matching.PATTERN_CLASSES)


@pytest.mark.parametrize(
    ("text", "classes"),
    [
        ("Żąda zadośćuczynienia 100 zł.", ("request",)),
        ("Zasądza zadośćuczynienie 100 zł.", ("judgment",)),
        ("Żąda zasądzenia 100 zł.", ("judgment", "request")),
        ("Przyznano 100 zł.", ("judgment", "request")),
    ],
)
def test_role_specific_stems_take_precedence_over_shared_words(text, classes):
    """
    Restrict a known role even when the sentence also contains a shared benefit word.

    args:
        text: Candidate sentence with monetary evidence.
        classes: Eligible embedding classes.

    returns:
        None.
    """
    groups = {
        "judgment": ["zasądz"],
        "request": ["żąda"],
        "shared": ["przyzna", "zadośćuczyn"],
    }
    rows = target_matching.candidate_sentences(text, groups)
    assert rows[0]["classes"] == classes


@pytest.mark.parametrize(
    ("text", "group", "stem"),
    [
        ("Wypłacono już 100 zł.", "prior_payment", "wypłac"),
        ("Koszty procesu wyniosły 100 zł.", "procedural_costs", "koszt"),
        ("Naliczono 100 zł odsetek.", "other_payments", "odset"),
        ("Utrzymał się z żądaniem do 100 zł.", "mixed", "utrzyma"),
    ],
)
def test_exclusion_keywords_also_select_sentences_before_embedding(text, group, stem):
    """
    Admit excluded payment contexts without requiring a positive target keyword.

    args:
        text: Monetary sentence belonging to an exclusion group.
        group: Eligible exclusion class.
        stem: Word prefix selecting that class.

    returns:
        None.
    """
    groups = {key: [] for key in (*target_matching.PATTERN_CLASSES, "shared")}
    groups[group] = [stem]
    (row,) = target_matching.candidate_sentences(text, groups)
    assert row["classes"] == (group,)
    assert text[row["start"] : row["end"]] == text






def test_amount_windows_keep_five_words_on_both_sides_and_can_overlap():
    """Preserve each independent amount anchor and exact bounded source context.

    args:
        None.

    returns:
        None.
    """
    text = "Wstęp.\nZasądza jeden dwa trzy cztery pięć sześć 10 000,50 zł siedem osiem 200 zł dziewięć dziesięć jedenaście dwanaście trzynaście czternaście."
    rows = target_matching.candidate_sentences(text, KEYWORDS)
    assert len(rows) == 2
    first, second = rows
    assert first["text"].startswith("dwa trzy cztery pięć sześć 10 000,50 zł")
    assert first["text"].endswith("siedem osiem 200 zł dziewięć")
    assert first["end"] > second["start"]
    for row, amount in zip(rows, ["10 000,50 zł", "200 zł"], strict=True):
        assert text[row["start"]:row["end"]] == row["text"]
        assert text[row["amount_start"]:row["amount_end"]] == amount
        assert text[row["sentence"]["start"]:row["sentence"]["end"]] == row["sentence"]["text"]
