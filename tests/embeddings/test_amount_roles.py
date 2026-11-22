"""Amount-level exclusion priority and complete operative totals."""

import asyncio
from types import SimpleNamespace

import torch
import pytest

from saos_dataset.embeddings.target_matching import TargetMatcher, candidate_sentences, prepare_text
from saos_dataset.extraction.model.configuration import load_config
from saos_dataset.extraction.targets import target_extraction


def test_above_threshold_exclusion_blocks_a_higher_target_score(monkeypatch):
    """Assign a window once when a non-target role clears the configured threshold.

    args:
        monkeypatch: Capture similarity calls to ensure no target comparison follows.

    returns:
        None.
    """
    config = load_config()
    config["embedding"]["device"] = "cpu"
    patterns = {label: [phrases[0]] for label, phrases in config["target_patterns"].items()}
    count = 0

    def encode(texts):
        """Return correlated target/cost patterns and target-aligned source vectors.

        args:
            texts: Prepared patterns or source windows.

        returns:
            Controlled two-dimensional embeddings.
        """
        nonlocal count
        count += 1
        if count == 1:
            return torch.tensor([[1.0, 0.0] if label == "judgment" else [0.9, 0.4] if label == "procedural_costs" else [-1.0, 0.0] for label in patterns])
        return torch.tensor([[1.0, 0.0] for _ in texts])

    from saos_dataset.embeddings import cosine_similarity as cosine_module

    original = cosine_module.cosine_similarity
    comparisons = []

    def compare(first, second, **kwargs):
        """Record each pattern phase while retaining actual cosine calculations.

        args:
            first: Source embedding matrix.
            second: Eligible pattern matrix.
            kwargs: Device selection.

        returns:
            Pairwise cosine similarities.
        """
        comparisons.append(len(second))
        return original(first, second, **kwargs)

    monkeypatch.setattr(cosine_module, "cosine_similarity", compare)
    matcher = TargetMatcher(config["embedding"], patterns, SimpleNamespace(encode=encode))
    result = matcher.match("Zasądza 100 zł po rozliczeniu zobowiązania.")
    assert result["judgment"] is None
    assert result["procedural_costs"]["similarity"] > 0.85
    assert comparisons == [5]


def test_operative_amount_anchors_sum_components_and_count_distinct_recipients(monkeypatch):
    """Sum separate principal awards without including their interest bases or duplicates.

    args:
        monkeypatch: Controlled matcher output.

    returns:
        None.
    """
    text = "WYROK\n1. Zasądza na rzecz A. B. kwotę 100 zł z odsetkami od kwoty 50 zł.\n2. Zasądza na rzecz C. D. kwotę 200 zł.\n3. Zasądza na rzecz A. B. kwotę 30 zł.\nUZASADNIENIE"
    config = load_config()
    rows = [row for row in candidate_sentences(text, config["embedding"]["candidate_keywords"]) if row["operative"] and row["first_amount"]]
    rows = [{**row, "similarity": 0.95} for row in rows]
    selected = {**rows[0], "awards": [*rows, rows[0]]}
    monkeypatch.setattr(target_extraction, "match_targets", lambda *args: {"judgment": selected, "request": None})
    result = asyncio.run(target_extraction.extract_targets(None, text, config))
    assert result["suma"] == "330"
    assert result["injured_party_count"] == 2
    assert result["beneficiaries"] == ["A. B.", "C. D."]


def test_embedding_normalization_preserves_source_but_ignores_amount_spelling():
    """Avoid scoring repeated written-out values and anonymized identity fragments.

    args:
        None.

    returns:
        None.
    """
    assert prepare_text("rzecz powoda A. B. (1) kwotę 20.500zł (dwadzieścia tysięcy pięćset złotych)") == "rzecz powoda kwotę 100 zł"


def test_unchanged_appeal_is_rejected_without_loading_models(monkeypatch):
    """Exclude upheld earlier awards even when their amounts appear in the reasoning.

    args:
        monkeypatch: Guard against model loading.

    returns:
        None.
    """
    from saos_dataset.embeddings import target_matching
    from saos_dataset.extraction import basal_filtering

    text = "WYROK\nI. oddala apelację;\nII. zasądza 5400 zł tytułem zwrotu kosztów procesu.\nUZASADNIENIE\nWcześniej zasądzono 100000 zł."
    monkeypatch.setattr(target_matching, "cached_matcher", lambda *args: (_ for _ in ()).throw(AssertionError("Unexpected model loading")))
    result = asyncio.run(basal_filtering.extract(None, text, load_config(overrides={"debug": True}), 42))
    assert result["award"]["excluded"]
    assert result["award"]["status"] == "appeal contains no new principal award"
    assert "features" not in result


@pytest.mark.parametrize("conflicting_role", [False, True])
def test_partial_operative_total_cannot_pass_when_another_principal_is_unmatched(conflicting_role):
    """Reject an incomplete case total rather than silently retaining one beneficiary.

    args:
        conflicting_role: Whether a non-target score conflicts with the operative amount.

    returns:
        None.
    """
    config = load_config()
    config["embedding"]["device"] = "cpu"
    patterns = {label: [phrases[0]] for label, phrases in config["target_patterns"].items()}
    calls = 0

    def encode(texts):
        """Supply a strong first award and a second award below the threshold.

        args:
            texts: Prepared patterns or windows.

        returns:
            Two-dimensional embeddings with controlled target similarity.
        """
        nonlocal calls
        calls += 1
        if calls == 1:
            return torch.tensor([[1., 0.] if label == "judgment" else [0., 1.] if label == "request" and conflicting_role else [-1., 0.] for label in patterns])
        return torch.tensor([[0., 1.] if text.startswith("Przyznaje") and conflicting_role else [0.8, 0.6] if text.startswith("Przyznaje") else [1., 0.] for text in texts])

    matcher = TargetMatcher(config["embedding"], patterns, SimpleNamespace(encode=encode))
    assert matcher.match("Zasądza 100 zł.\nPrzyznaje 200 zł.")["judgment"] is None


def test_unmatched_current_principal_still_blocks_a_zero_target(monkeypatch):
    """Keep a low-scoring award unresolved rather than replacing it with another denial.

    args:
        monkeypatch: Controlled matcher without accepted monetary windows.

    returns:
        None.
    """
    from saos_dataset.embeddings import target_matching

    empty = dict.fromkeys(target_matching.PATTERN_CLASSES)
    matcher = SimpleNamespace(match=lambda text: empty, match_denial=lambda text: (_ for _ in ()).throw(AssertionError("Current principal forbids zero")))
    monkeypatch.setattr(target_matching, "cached_matcher", lambda *args: matcher)
    result = target_matching.match_targets("Zasądza 100 zł.\nOddala powództwo w całości.", load_config())
    assert result["judgment-denial"] is None


def test_varied_principal_interest_and_procedural_contexts_remain_distinct():
    """Apply general role guards across amounts, wording and currency spellings.

    args:
        None.

    returns:
        None.
    """
    config = load_config()
    for amount in ["123 PLN", "12 345,67 zł", "1,5 tys. złotych"]:
        for interest in ["z odsetkami ustawowymi", "wraz z należnymi ustawowymi odsetkami", "z ustawowymi odsetkami za opóźnienie"]:
            text = f"Zasądza na rzecz powoda A. B. kwotę {amount} {interest}."
            row = candidate_sentences(text, config["embedding"]["candidate_keywords"])[0]
            assert "judgment" in row["classes"]
            assert "other_payments" not in row["classes"]
        for expense in ["zwrotu kosztów postępowania", "zwrotu kosztów sądowych", "kosztów zastępstwa procesowego"]:
            text = f"Zasądza na rzecz powoda C. D. kwotę {amount} tytułem {expense}."
            row = candidate_sentences(text, config["embedding"]["candidate_keywords"])[0]
            assert row["procedural"]
            assert "judgment" not in row["classes"]


def test_modified_appeal_with_current_principal_is_not_excluded(monkeypatch):
    """Keep appellate rulings that award principal while dismissing the remaining appeal.

    args:
        monkeypatch: Controlled accepted-current-award matcher.

    returns:
        None.
    """
    from saos_dataset.embeddings import target_matching

    text = "WYROK\nI. zmienia wyrok w ten sposób, że zasądza na rzecz A. B. kwotę 1000 zł.\nII. oddala apelację w pozostałej części.\nUZASADNIENIE"
    expected = {**dict.fromkeys(target_matching.PATTERN_CLASSES), "judgment": {"operative": True}}
    matcher = SimpleNamespace(match=lambda value: expected)
    monkeypatch.setattr(target_matching, "cached_matcher", lambda *args: matcher)
    assert target_matching.match_targets(text, load_config()) is expected


@pytest.mark.parametrize("text", [
    "Zasądza na rzecz Skarbu Państwa kwotę 12345 PLN tytułem odszkodowania za szkodę majątkową.",
    "Zasądza odszkodowanie za koszty leczenia potwierdzone przez biegłego w kwocie 12345 zł.",
])
def test_party_names_and_experts_alone_do_not_establish_procedural_costs(text):
    """Require expense-role wording rather than merely a public party or expert mention.

    args:
        text: Principal claim mentioning a public party or an evidentiary expert.

    returns:
        None.
    """
    row = candidate_sentences(text, load_config()["embedding"]["candidate_keywords"])[0]
    assert not row["procedural"]
    assert "judgment" in row["classes"]
