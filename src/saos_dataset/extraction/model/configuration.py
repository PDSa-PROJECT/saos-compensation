"""Validation and assembly of extraction configuration."""

import copy
from pathlib import Path

from saos_dataset.configuration import read_config

from saos_dataset.embeddings.settings import TargetSettings
from saos_dataset.settings import RuntimeSettings
from .prompts import DEFAULTS
from .settings import BasalSettings, FeatureSettings, MODEL_REVISIONS

ROOT = Path(__file__).resolve().parents[4]


def load_config(directory=None, overrides=None):
    """
    Validate configuration and assemble effective extraction settings.

    args:
        directory: Input or output directory for this operation.
        overrides: Explicit local processing overrides, above environment and dotenv.

    returns:
        Effective validated configuration.
    """
    from saos_dataset.processing.settings import validate_settings as validate_processing_settings

    directory = (
        Path(directory)
        if directory is not None
        else ROOT / "configs" / "dataset" / "processing"
    )
    basal = read_config(directory / "basal.yaml")
    processing = read_config(directory / "process.yaml")
    features = read_config(directory / "features.yaml")
    targets = read_config(directory / "targets.yaml")
    overrides = overrides or {}
    runtime = RuntimeSettings(**{
        "processing_" + key: value for key, value in overrides.items()
        if "processing_" + key in RuntimeSettings.model_fields
    })
    processing = runtime.merge("processing", processing)
    basal = runtime.merge("basal", basal)
    embedding = targets.get("embedding")
    if (
        runtime.embedding_model is not None
        and isinstance(embedding, dict)
        and runtime.embedding_model != embedding.get("model")
        and runtime.embedding_revision is None
    ):
        raise ValueError("EMBEDDING_REVISION is required when EMBEDDING_MODEL changes")
    targets = {**targets, "embedding": runtime.merge("embedding", embedding)}
    features = FeatureSettings.from_mapping(features)
    targets = TargetSettings.from_mapping(targets)
    processing.update(overrides)
    validate_processing_settings(processing)
    basal = BasalSettings.from_mapping(basal)
    config = {
        **copy.deepcopy(DEFAULTS),
        "processing": processing,
        "embedding": targets.embedding.model_dump(),
        "target_patterns": targets.patterns,
        "fields": features.text_fields,
        "metadata_fields": features.metadata_fields,
        "target_fields": ["suma"],
    }
    config["system_one"].update(
        model=basal.model, revision=MODEL_REVISIONS[basal.model]
    )
    config["system_one"]["mode"] = "mps" if basal.device == "mps" else "eager"
    config["system_one"]["device"] = basal.device
    config["system_one"].update(
        {
            key: value
            for key, value in basal.model_dump().items()
            if key in (
                "minimum_probability",
                "maximum_leak_probability",
                "amount_minimum_probability",
            )
        }
    )
    return config
