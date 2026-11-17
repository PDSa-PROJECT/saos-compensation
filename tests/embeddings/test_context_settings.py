"""Configurable monetary context boundaries and strict YAML validation."""

import pytest
import yaml

from dataset.embeddings.target_matching import TargetMatcher, candidate_sentences
from dataset.extraction.model.configuration import load_config


@pytest.mark.parametrize("before,after,expected", [
    (2, 1, "trzy cztery 100 zł pięć"),
    (0, 0, "100 zł"),
    (0, 2, "100 zł pięć sześć"),
    (2, 0, "trzy cztery 100 zł"),
    (50, 50, "Zasądza jeden dwa trzy cztery 100 zł pięć sześć siedem."),
])
def test_configured_context_keeps_exact_source_offsets(before, after, expected):
    """Support asymmetric and empty context without changing the amount or clause.

    args:
        before: Words retained before the amount.
        after: Words retained after the amount.
        expected: Exact selected source window.

    returns:
        None.
    """
    text = "Zasądza jeden dwa trzy cztery 100 zł pięć sześć siedem."
    config = load_config()
    row, = candidate_sentences(text, config["embedding"]["candidate_keywords"], context_words_before=before, context_words_after=after)
    assert row["text"] == expected
    assert text[row["start"]:row["end"]] == expected
    assert text[row["amount_start"]:row["amount_end"]] == "100 zł"
    assert row["sentence"]["text"] == text


@pytest.mark.parametrize("field", ["context_words_before", "context_words_after"])
@pytest.mark.parametrize("value", [-1, True, 1.5, "2", None])
def test_context_counts_require_nonnegative_yaml_integers(config_directory, field, value):
    """Reject malformed experiment values at configuration loading before inference.

    args:
        config_directory: Isolated processing configuration.
        field: Context count to invalidate.
        value: Unsupported count value.

    returns:
        None.
    """
    path = config_directory / "targets.yaml"
    settings = yaml.safe_load(path.read_text())
    settings["embedding"][field] = value
    path.write_text(yaml.safe_dump(settings, allow_unicode=True))
    with pytest.raises(ValueError):
        load_config(config_directory)


def test_matcher_uses_yaml_context_for_embeddings(config_directory):
    """Apply asymmetric YAML values to the text actually passed to the encoder.

    args:
        config_directory: Isolated processing configuration.

    returns:
        None.
    """
    import torch

    path = config_directory / "targets.yaml"
    settings = yaml.safe_load(path.read_text())
    settings["embedding"].update(context_words_before=2, context_words_after=1)
    path.write_text(yaml.safe_dump(settings, allow_unicode=True))
    config = load_config(config_directory)
    config["embedding"]["device"] = "cpu"
    captured = []

    class Encoder:
        def encode(self, texts):
            """Record windows while returning constant embeddings for routing.

            args:
                self: Recording encoder.
                texts: Pattern templates or source windows.

            returns:
                Nonzero embeddings with the requested batch shape.
            """
            captured.append(texts)
            return torch.ones((len(texts), 2))

    matcher = TargetMatcher(config["embedding"], config["target_patterns"], Encoder())
    matcher.match("Zasądza jeden dwa trzy cztery 100 zł pięć sześć siedem.")
    assert captured[1] == ["trzy cztery 100 zł pięć"]


@pytest.mark.parametrize("after,expected", [(0, "Zasądza 100 zł"), (50, "Zasądza 100 zł.")])
def test_oversized_context_stops_at_sentence_boundaries(after, expected):
    """Use the whole short sentence without borrowing words from neighboring sentences.

    args:
        after: Independent forward context limit.
        expected: Source window bounded by the selected sentence.

    returns:
        None.
    """
    text = "Poprzednie zdanie. Zasądza 100 zł. Następne zdanie."
    config = load_config()
    row, = candidate_sentences(text, config["embedding"]["candidate_keywords"], context_words_before=50, context_words_after=after)
    assert row["text"] == expected
    assert text[row["start"]:row["end"]] == expected
