"""Validation and assembly of extraction configuration."""

import copy
import math
import re
from pathlib import Path

from ...configuration import read_config

from ...embeddings.target_matching import validate_settings
from .prompts import DEFAULTS, METADATA_FIELDS

ROOT = Path(__file__).resolve().parents[4]


def load_config(directory=None, overrides=None):
    """
    Validate configuration and assemble effective extraction settings.

    args:
        directory: Input or output directory for this operation.
        overrides: Explicit local processing overrides.

    returns:
        Effective validated configuration.
    """
    from ...processing.settings import validate_settings as validate_processing_settings

    directory = (
        Path(directory)
        if directory is not None
        else ROOT / "configs" / "dataset" / "processing"
    )
    basal = read_config(directory / "basal.yaml")
    processing = read_config(directory / "process.yaml")
    features = read_config(directory / "features.yaml")
    targets = read_config(directory / "targets.yaml")
    if set(targets) != {"embedding", "patterns"}:
        raise ValueError("targets.yaml requires embedding and patterns")
    embedding, patterns = targets["embedding"], targets["patterns"]
    if set(features) != {"metadata_fields", "text_fields"}:
        raise ValueError(
            "features.yaml requires metadata_fields and text_fields"
        )
    metadata = features["metadata_fields"]
    if (
        not isinstance(metadata, list)
        or any(
            not isinstance(field, str) or field not in METADATA_FIELDS
            for field in metadata
        )
        or len(metadata) != len(set(metadata))
    ):
        raise ValueError("Invalid metadata_fields")
    fields = features["text_fields"]
    if (
        not isinstance(fields, dict)
        or not fields
        or any(
            not isinstance(name, str)
            or re.fullmatch(r"[a-z][a-z0-9_]*", name) is None
            or name in METADATA_FIELDS
            or not isinstance(question, str)
            or not question.strip()
            for name, question in fields.items()
        )
    ):
        raise ValueError(
            "text_fields must be nonempty and map field names to nonempty questions"
        )
    if "damage" not in fields:
        raise ValueError("text_fields must include damage")
    validate_settings(embedding, patterns)
    processing.update(overrides or {})
    validate_processing_settings(processing)
    required = {
        "model",
        "device",
        "minimum_probability",
        "maximum_leak_probability",
        "amount_minimum_probability",
    }
    if set(basal) != required:
        raise ValueError(
            "basal.yaml requires model, device and three probability thresholds"
        )
    revisions = {
        "Remek/basal-2.0-mini": "cb81b32ce89b0b87e62fcdad28f0435e25c953f3",
        "Remek/basal-2.0-4.5B": "e5ba9149760d99b73b1963d8e0ccf948b58afacb",
    }
    if not isinstance(basal["model"], str) or basal["model"] not in revisions:
        raise ValueError("model must be Remek/basal-2.0-mini or Remek/basal-2.0-4.5B")
    if basal["device"] not in ("cpu", "cuda", "mps"):
        raise ValueError("device must be cpu, cuda or mps")
    for key in (
        "minimum_probability",
        "maximum_leak_probability",
        "amount_minimum_probability",
    ):
        value = basal[key]
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not 0 <= value <= 1
        ):
            raise ValueError(f"Invalid probability threshold: {key}")
    config = {
        **copy.deepcopy(DEFAULTS),
        "processing": processing,
        "embedding": embedding,
        "target_patterns": patterns,
        "fields": fields,
        "metadata_fields": metadata,
        "target_fields": ["suma"],
    }
    config["system_one"].update(
        model=basal["model"], revision=revisions[basal["model"]]
    )
    config["system_one"]["mode"] = "mps" if basal["device"] == "mps" else "eager"
    config["system_one"]["device"] = basal["device"]
    config["system_one"].update(
        {
            key: basal[key]
            for key in (
                "minimum_probability",
                "maximum_leak_probability",
                "amount_minimum_probability",
            )
        }
    )
    return config
