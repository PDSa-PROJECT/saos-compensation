"""Amount-level exclusion priority and complete operative totals."""

import asyncio
from types import SimpleNamespace

import torch

from dataset.embeddings.target_matching import TargetMatcher, candidate_sentences, prepare_text
from dataset.extraction.model.configuration import load_config
from dataset.extraction.targets import target_extraction


def test_above_threshold_exclusion_blocks_a_higher_target_score():
    """Assign a window once when a non-target role clears the configured threshold.

    args:
        None.

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

    matcher = TargetMatcher(config["embedding"], patterns, SimpleNamespace(encode=encode))
    result = matcher.match("Zasądza 100 zł po rozliczeniu zobowiązania.")
    assert result["judgment"] is None
    assert result["procedural_costs"]["similarity"] > 0.85


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
    from dataset.embeddings import target_matching
    from dataset.extraction import basal_filtering

    text = "WYROK\nI. oddala apelację;\nII. zasądza 5400 zł tytułem zwrotu kosztów procesu.\nUZASADNIENIE\nWcześniej zasądzono 100000 zł."
    monkeypatch.setattr(target_matching, "cached_matcher", lambda *args: (_ for _ in ()).throw(AssertionError("Unexpected model loading")))
    result = asyncio.run(basal_filtering.extract(None, text, load_config(overrides={"debug": True}), 42))
    assert result["award"]["excluded"]
    assert result["award"]["status"] == "appeal contains no new principal award"
    assert "features" not in result


def test_partial_operative_total_cannot_pass_when_another_principal_is_unmatched():
    """Reject an incomplete case total rather than silently retaining one beneficiary.

    args:
        None.

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
            return torch.tensor([[1., 0.] if label == "judgment" else [-1., 0.] for label in patterns])
        return torch.tensor([[0.8, 0.6] if text.startswith("Przyznaje") else [1., 0.] for text in texts])

    matcher = TargetMatcher(config["embedding"], patterns, SimpleNamespace(encode=encode))
    assert matcher.match("Zasądza 100 zł.\nPrzyznaje 200 zł.")["judgment"] is None
