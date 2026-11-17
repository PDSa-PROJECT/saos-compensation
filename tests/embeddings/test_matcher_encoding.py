"""Sentence encoding and configured tail truncation without model downloads."""

from types import SimpleNamespace

import pytest
import torch

from dataset.embeddings.encoding import SentenceEncoder


def test_sentences_are_encoded_once_with_tail_truncation_and_masked_pooling():
    """Keep fitting sentences whole and truncate only tails beyond the token limit.

    args:
        None.

    returns:
        None.
    """
    encoder = SentenceEncoder.__new__(SentenceEncoder)
    encoder.settings = {"device": "cpu", "batch_size": 2, "max_length": 512}
    calls, shapes = [], []

    def tokenize(texts, *, padding, truncation, max_length, return_tensors):
        """Represent each input character as one token before tail truncation.

        args:
            texts: Source sentences in the current batch.
            padding: Whether shorter inputs receive padding.
            truncation: Whether overlength tails are removed.
            max_length: Maximum number of tokens per sentence.
            return_tensors: Requested tensor format.

        returns:
            Padded token IDs and their attention mask.
        """
        assert padding is True and truncation is True
        assert max_length == 512 and return_tensors == "pt"
        calls.extend(texts)
        lengths = [min(len(text), max_length) for text in texts]
        tokens = torch.zeros((len(texts), max(lengths)), dtype=torch.long)
        mask = torch.zeros_like(tokens)
        for index, length in enumerate(lengths):
            tokens[index, :length] = torch.arange(1, length + 1)
            mask[index, :length] = 1
        return {"input_ids": tokens, "attention_mask": mask}

    class Model:
        """Expose deterministic token vectors for sentence pooling."""

        def __call__(self, input_ids, attention_mask):
            """Return two identical coordinates per token, including padding.

            args:
                input_ids: Padded token IDs for this batch.
                attention_mask: Nonpadding mask used by the encoder.

            returns:
                Token-level hidden states.
            """
            shapes.append(tuple(input_ids.shape))
            return SimpleNamespace(
                last_hidden_state=input_ids.float().unsqueeze(-1).repeat(1, 1, 2)
            )

    encoder.tokenizer = tokenize
    encoder.model = Model()
    texts = ["a" * 130, "b" * 600, "cc"]
    torch.testing.assert_close(
        encoder.encode(texts),
        torch.tensor([[65.5, 65.5], [256.5, 256.5], [1.5, 1.5]]),
    )
    assert calls == texts
    assert shapes == [(2, 512), (1, 2)]


@pytest.mark.parametrize(
    "length,spans",
    [
        (10, [(0, 10)]),
        (510, [(0, 510)]),
        (511, [(0, 510), (254, 511)]),
        (764, [(0, 510), (254, 764)]),
        (1026, [(0, 510), (254, 764), (508, 1018), (762, 1026)]),
    ],
)
def test_sentence_views_cover_all_tokens_with_configured_overlap(length, spans):
    """Preserve complete coverage, overlap and exact source offsets at window boundaries.

    args:
        length: Number of source tokens represented by individual characters.
        spans: Expected source windows excluding special tokens.

    returns:
        None.
    """
    class Tokenizer:
        """Model tokenizer overflow and sentence boundary tokens without loading weights."""

        def __call__(self, text, **kwargs):
            """Return token offsets in overlapping windows including special tokens.

            args:
                text: Original sentence.
                kwargs: Tokenizer window settings supplied by the encoder.

            returns:
                Per-window source offsets with zero-width special tokens.
            """
            assert kwargs == {
                "truncation": True,
                "max_length": 512,
                "stride": 256,
                "return_overflowing_tokens": True,
                "return_offsets_mapping": True,
                "verbose": False,
            }
            windows = []
            for start in range(0, len(text), 254):
                end = min(start + 510, len(text))
                windows.append([(0, 0)] + [(i, i + 1) for i in range(start, end)] + [(0, 0)])
                if end == len(text):
                    break
            return {"offset_mapping": windows}

        def num_special_tokens_to_add(self):
            """Reserve the two sentence boundary tokens.

            args:
                None.

            returns:
                Number of special tokens.
            """
            return 2

    encoder = SentenceEncoder.__new__(SentenceEncoder)
    encoder.settings = {"max_length": 512}
    encoder.tokenizer = Tokenizer()
    text = "a" * length
    views = encoder.sentence_views(text, 256)
    assert [(row["start"], row["end"]) for row in views] == spans
    assert all(text[row["start"]:row["end"]] == row["text"] for row in views)
    assert set(range(length)) == {i for row in views for i in range(row["start"], row["end"])}
    assert all(left["end"] - right["start"] == 256 for left, right in zip(views, views[1:]))


@pytest.mark.parametrize("overlap", [-1, 510, 512, True, 0.5, "256", None])
def test_window_overlap_must_fit_source_token_capacity(overlap):
    """Reject overlap values that cannot produce a valid advancing token window.

    args:
        overlap: Invalid overlap value.

    returns:
        None.
    """
    encoder = SentenceEncoder.__new__(SentenceEncoder)
    encoder.settings = {"max_length": 512}
    encoder.tokenizer = SimpleNamespace(num_special_tokens_to_add=lambda: 2)
    with pytest.raises(ValueError, match="window_overlap"):
        encoder.sentence_views("Source sentence.", overlap)
