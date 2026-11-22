"""Apply existing Basal predictors and admission to target-enriched rows."""

import asyncio
import json
from pathlib import Path

from zenml import pipeline, step
from zenml.client import Client

from saos_dataset.clients.basal import open_server
from saos_dataset.extraction.basal_filtering import extract_predictors
from saos_dataset.extraction.model.configuration import load_config
from saos_dataset.extraction.quality import admission_decision, target_rejection_reason
from saos_dataset.processing.metadata import add_metadata_features
from saos_dataset.processing.localities import load_locality_context
from saos_dataset.processing.pipeline import check_device

from saos_workflows.artifacts import ParquetArtifact, ParquetMaterializer, read_artifact, write_artifact


async def extract_feature_rows(rows, config, server, *, localities=None, extractor=None):
    """Apply existing predictor and admission rules without repeating target matching.

    args:
        rows: Target-enriched judgment mappings with original source rows intact.
        config: Validated extraction settings.
        server: Existing async Basal inference server, or a controlled fake.
        localities: Optional locality matching context for configured metadata.
        extractor: Optional async target-prepared predictor callable.
    returns:
        Judgment mappings preserving every source row and feature decision.
    """
    extractor = extract_predictors if extractor is None else extractor
    output = []
    for row in rows:
        if row["selection_status"] != "selected":
            output.append({**row, "eligible": False})
            continue
        if row["features_json"] is not None or row["eligible"] is not None:
            raise ValueError(f"Features already present for SAOS ID {row['saos_id']}")
        if row["target_json"] is None:
            raise ValueError(f"Missing target extraction for SAOS ID {row['saos_id']}")
        award = json.loads(row["target_json"])
        target_reason = target_rejection_reason(award, config)
        if award.get("excluded") or (target_reason and not config["processing"]["debug"]):
            output.append({**row, "eligible": False, "features_json": json.dumps({
                "feature_status": "skipped", "feature_reason": target_reason or award.get("status")
            }, ensure_ascii=False)})
            continue
        record = json.loads(row["selected_record_json"])
        if record["id"] != row["saos_id"] or record["text"] != row["judgment_text"]:
            raise ValueError(f"Selected record does not match source row {row['saos_id']}")
        result = await extractor(server, record["text"], config, row["saos_id"], award)
        retained, reason = admission_decision(result, config)
        accepted = reason is None
        if retained:
            add_metadata_features(result, record, config["metadata_fields"], localities)
        payload = {key: value for key, value in result.items() if key != "award"}
        payload.update(feature_status="accepted" if accepted else "rejected", feature_reason=reason)
        output.append({**row, "features_json": json.dumps(payload, ensure_ascii=False, allow_nan=False),
                       "eligible": accepted})
    return output


async def extract_with_worker(rows, config):
    """Reuse one local Basal worker and optional locality snapshot for selected cases.

    args:
        rows: Explicitly selected target-enriched judgment mappings.
        config: Validated processing and model configuration.
    returns:
        Feature-enriched judgment mappings.
    """
    if not any(
        row["selection_status"] == "selected"
        and row["target_json"] is not None
        and not json.loads(row["target_json"]).get("excluded")
        and (config["processing"]["debug"] or target_rejection_reason(json.loads(row["target_json"]), config) is None)
        for row in rows
    ):
        return await extract_feature_rows(rows, config, None)
    localities = load_locality_context(
        config["metadata_fields"], config["paths"]["localities_path"], config["processing"]["timeout"]
    )
    check_device(config["system_one"]["device"])
    async with open_server(config["system_one"], Path(config["paths"]["model_cache_path"])) as server:
        return await extract_feature_rows(rows, config, server, localities=localities)


@step(enable_cache=False, output_materializers=ParquetMaterializer)
def extract_features_step(cases: ParquetArtifact, config_dir: str | None = None) -> ParquetArtifact:
    """Publish predictors and admission decisions as managed Parquet.

    args:
        cases: Explicitly selected target-enriched artifact.
        config_dir: Optional existing processing YAML directory.
    returns:
        Parquet reference published through the configured artifact store.
    """
    config = load_config(config_dir)
    result = asyncio.run(extract_with_worker(read_artifact(cases), config))
    return write_artifact(result)


@pipeline
def extract_features(artifact_id: str, config_dir: str | None = None) -> ParquetArtifact:
    """Track source-grounded feature extraction and admission.

    args:
        artifact_id: Exact target artifact-version UUID, never implicit latest.
        config_dir: Optional existing processing YAML directory.
    returns:
        Published feature-enriched artifact output.
    """
    return extract_features_step(cases=Client().get_artifact_version(artifact_id), config_dir=config_dir)
