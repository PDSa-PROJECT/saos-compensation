"""Reusable text embeddings with lazy, cached model loading."""

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENCODER_SETTINGS = ("model", "revision", "device", "batch_size", "max_length")


def validate_settings(settings):
    """Validate encoder settings independently of target-matching configuration.

    args:
        settings: Mapping with model, revision, device, batch_size and max_length.

    returns:
        None.
    """
    if not isinstance(settings, dict) or not set(ENCODER_SETTINGS) <= set(settings):
        raise ValueError(f"Embedding settings require {list(ENCODER_SETTINGS)}")
    for key in ("model", "revision"):
        if not isinstance(settings[key], str) or not settings[key].strip():
            raise ValueError(f"Invalid embedding {key}")
    if settings["device"] not in ("cpu", "mps", "cuda"):
        raise ValueError("Embedding device must be cpu, mps or cuda")
    for key in ("batch_size", "max_length"):
        if type(settings[key]) is not int or settings[key] <= 0:
            raise ValueError(f"Embedding {key} must be a positive integer")
    if settings["max_length"] < 4:
        raise ValueError("Embedding max_length must accommodate special tokens and text")


class SentenceEncoder:
    """Mean-pooled sentence embeddings within the configured model context."""

    def __init__(self, settings):
        """
        Load the pinned tokenizer and model into the selected PyTorch device.

        args:
            settings: Validated embedding configuration.

        returns:
            None.
        """
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.settings = settings
        device = settings["device"]
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("Embedding CUDA was requested but is unavailable")
        if device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("Embedding MPS was requested but is unavailable")
        options = {
            "revision": settings["revision"],
            "cache_dir": ROOT / "embedding_weights",
        }
        self.tokenizer = AutoTokenizer.from_pretrained(settings["model"], **options)
        self.model = (
            AutoModel.from_pretrained(
                settings["model"], use_safetensors=True, **options
            )
            .to(device)
            .eval()
        )
        if settings["max_length"] > self.model.config.max_position_embeddings:
            raise ValueError("Embedding max_length exceeds the model context")

    def sentence_views(self, text):
        """Keep a fitting sentence whole or return its beginning and ending separately.

        args:
            text: Original source sentence.

        returns:
            One or two text spans with offsets relative to the original sentence.
        """
        tokens = self.tokenizer(
            text, add_special_tokens=False, truncation=False,
            return_offsets_mapping=True, verbose=False,
        )
        limit = self.settings["max_length"] - self.tokenizer.num_special_tokens_to_add()
        offsets = tokens["offset_mapping"]
        spans = [(0, len(text))] if len(offsets) <= limit else [
            (0, offsets[limit - 1][1]), (offsets[-limit][0], len(text))
        ]
        return [{"text": text[start:end], "start": start, "end": end} for start, end in spans]

    def encode(self, texts):
        """
        Encode each sentence once, truncating its tail beyond the configured limit.

        args:
            texts: Nonempty list of texts to encode.

        returns:
            Float32 embedding matrix on the configured device.
        """
        import torch

        device = self.settings["device"]
        vectors = []
        with torch.inference_mode():
            for start in range(0, len(texts), self.settings["batch_size"]):
                end = start + self.settings["batch_size"]
                tokens = self.tokenizer(
                    texts[start:end],
                    padding=True,
                    truncation=True,
                    max_length=self.settings["max_length"],
                    return_tensors="pt",
                )
                batch = {
                    key: value.to(device) for key, value in tokens.items()
                }
                output = self.model(**batch).last_hidden_state.float()
                mask = batch["attention_mask"].unsqueeze(-1).float()
                vectors.append((output * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1))
        return torch.cat(vectors)


@lru_cache(maxsize=1)
def cached_encoder(settings_json):
    """Reuse one encoder for unchanged model and runtime settings.

    args:
        settings_json: Serialized encoder-only configuration.

    returns:
        Loaded sentence encoder.
    """
    return SentenceEncoder(json.loads(settings_json))


def create_embeddings(texts, settings):
    """Embed original texts without target-specific filtering or normalization.

    args:
        texts: Nonempty list of nonblank strings, retained in input order.
        settings: Model, revision, device, batch_size and max_length mapping;
            additional target-matching settings are ignored.

    returns:
        Float32 PyTorch tensor of shape (len(texts), model dimension) on the
        configured device. Text beyond max_length tokens is truncated at the tail.
    """
    validate_settings(settings)
    if not isinstance(texts, list) or not texts or any(
        not isinstance(text, str) or not text.strip() for text in texts
    ):
        raise ValueError("texts must be a nonempty list of nonblank strings")
    encoder = cached_encoder(
        json.dumps({key: settings[key] for key in ENCODER_SETTINGS}, sort_keys=True)
    )
    return encoder.encode(texts)
