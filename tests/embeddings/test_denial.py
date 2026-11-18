"""Full-text denial screening before monetary candidate selection."""

import math

import pytest
import torch

from dataset.embeddings import target_matching
from dataset.extraction.model.configuration import load_config


class Encoder:
    """Supply controlled denial similarities without loading model weights."""

    def __init__(self, scores, costs=None):
        """Store source scores and capture every encoding batch.

        args:
            scores: Source sentences mapped to their denial cosine similarities.
            costs: Optional source-to-cost similarities.

        returns:
            None.
        """
        self.scores = {target_matching.prepare_text(text): score for text, score in scores.items()}
        self.costs = {target_matching.prepare_text(text): score for text, score in (costs or {}).items()}
        self.calls = []

    def encode(self, texts):
        """Encode orthogonal patterns and unit vectors for source sentences.

        args:
            texts: Prepared pattern templates or source sentences.

        returns:
            Float32 vectors with a residual dimension outside all pattern axes.
        """
        self.calls.append(texts)
        if len(self.calls) == 1:
            self.width = len(texts) + 1
            self.cost_index = next(index for index, text in enumerate(texts) if "zwrotu kosztów procesu" in text)
            return torch.eye(self.width)[:-1]
        vectors = torch.zeros((len(texts), self.width))
        for index, text in enumerate(texts):
            score = self.scores[text]
            vectors[index, 0] = score
            cost = self.costs.get(text, 0)
            vectors[index, self.cost_index] = cost
            vectors[index, -1] = math.sqrt(max(0, 1 - score**2 - cost**2))
        return vectors


def make_matcher(scores, batch_size=2):
    """Build a denial matcher from the real pattern configuration and a fake encoder.

    args:
        scores: Sentence-to-denial-similarity mapping.
        batch_size: Maximum sentences evaluated before checking for early rejection.

    returns:
        Matcher, controlled encoder and CPU configuration.
    """
    config = load_config()
    config["embedding"].update(device="cpu", batch_size=batch_size)
    assert next(iter(config["target_patterns"])) == "judgment-denial"
    encoder = Encoder(scores)
    matcher = target_matching.TargetMatcher(
        config["embedding"], config["target_patterns"], encoder
    )
    return matcher, encoder, config


@pytest.mark.parametrize("score,threshold,denied", [(0.84, 0.85, False), (0.85, 0.85, False), (0.86, 0.85, True)])
def test_explicit_denial_has_a_strict_threshold(score, threshold, denied):
    """Require lexical dismissal evidence and a score strictly above the threshold.

    args:
        score: Controlled denial score.
        threshold: Minimum accepted score.
        denied: Expected result.

    returns:
        None.
    """
    text = "Oddala powództwo w całości."
    matcher, _, _ = make_matcher({text: score})
    matcher.settings["minimum_cosine_similarity"] = threshold
    assert (matcher.match_denial(text) is not None) is denied


@pytest.mark.parametrize("text", [
    "W związku z powyższym, Sąd zasądził na rzecz powoda pozostałą do zapłaty kwotę 110 000 zł tytułem zadośćuczynienia (punkt 1 wyroku).",
    "Zdaniem Sądu nie było podstaw do ustalenia wysokości zadośćuczynienia w kwocie zażądanej przez powódkę.",
    "Oddala powództwo w pozostałej części.", "Oddala apelację powoda.",
    "Pozwany wniósł o oddalenie powództwa w całości.", "Sąd nie oddalił powództwa.",
])
def test_non_denials_never_reach_the_encoder(text):
    """Block the reported false zeros and partial or requested dismissals before similarity.

    args:
        text: Sentence that cannot establish complete denial.

    returns:
        None.
    """
    matcher, encoder, _ = make_matcher({})
    assert matcher.match_denial(text) is None
    assert len(encoder.calls) == 1


def test_denial_keeps_the_best_match_across_all_batches():
    """Avoid early stopping at a weaker denial in an earlier batch.

    args:
        None.

    returns:
        None.
    """
    first, last = "Oddala powództwo.", "Sąd oddalił powództwo w całości."
    matcher, encoder, _ = make_matcher({first: 0.86, last: 0.96}, batch_size=1)
    result = matcher.match_denial(first + "\nOpis szkody.\n" + last)
    assert result["text"] == last
    assert result["similarity"] == pytest.approx(0.96)
    assert len(encoder.calls) == 3


def test_operative_award_cannot_be_overridden_by_reasoning_denial(monkeypatch):
    """Prefer a confirmed current award over a misleading dismissal in reasoning.

    args:
        monkeypatch: Controlled match routing.

    returns:
        None.
    """
    from types import SimpleNamespace

    result = {**dict.fromkeys(target_matching.PATTERN_CLASSES), "judgment": {"operative": True}}
    matcher = SimpleNamespace(match=lambda text: result, match_denial=lambda text: pytest.fail("Operative award already confirmed"))
    monkeypatch.setattr(target_matching, "cached_matcher", lambda *args: matcher)
    assert target_matching.match_targets("Zasądza 100 zł.\nUZASADNIENIE\nOddala powództwo w części.", load_config()) is result


@pytest.mark.parametrize("text", [
    "Powództwo zostało oddalone w całości.",
    "Sąd oddalił powództwo o odszkodowanie w całości.",
    "Powództwo podlegało oddaleniu w całości.",
    "Oddalono wszystkie roszczenia powoda.",
])
def test_explicit_denial_supports_different_grammatical_constructions(text):
    """Recognize varied complete dismissals independently of particular cases or sums.

    args:
        text: Explicit complete-dismissal construction.

    returns:
        None.
    """
    assert target_matching.explicit_denial(text)
