"""Sentence encoding and configured tail truncation without model downloads."""

from types import SimpleNamespace

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


def test_sentence_views_keep_whole_input_or_separate_beginning_and_ending():
    """Reserve special tokens and retain exact source spans for both long-sentence views.

    args:
        None.

    returns:
        None.
    """
    class Tokenizer:
        """Represent each character as one token with exact source offsets."""

        def __call__(self, text, **kwargs):
            """Expose every source character without truncating tokenization.

            args:
                text: Original sentence.
                kwargs: Tokenizer options supplied by the encoder.

            returns:
                Character-aligned token offsets.
            """
            assert kwargs == {
                "add_special_tokens": False,
                "truncation": False,
                "return_offsets_mapping": True,
                "verbose": False,
            }
            return {"offset_mapping": [(index, index + 1) for index in range(len(text))]}

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
    short = "a" * 510
    assert encoder.sentence_views(short) == [{"text": short, "start": 0, "end": 510}]
    text = "a" * 510 + "middle" + "b" * 510
    views = encoder.sentence_views(text)
    assert views == [
        {"text": "a" * 510, "start": 0, "end": 510},
        {"text": "b" * 510, "start": 516, "end": 1026},
    ]
    assert all(text[row["start"]:row["end"]] == row["text"] for row in views)
