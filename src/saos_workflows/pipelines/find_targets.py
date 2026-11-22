"""Apply existing target extraction to source-backed local judgment rows."""

import asyncio
import json
from decimal import Decimal

from zenml import pipeline, step
from zenml.client import Client

from saos_dataset.extraction.model.configuration import load_config
from saos_dataset.extraction.quality import target_rejection_reason
from saos_dataset.extraction.targets.amounts import extract_award

from saos_workflows.artifacts import ParquetArtifact, ParquetMaterializer, read_artifact, write_artifact


async def find_target_rows(rows, config, *, extractor=None):
    """Enrich selected rows without loading Basal or changing source columns.

    args:
        rows: Input judgment mappings with the shared ten-column schema.
        config: Validated extraction configuration.
        extractor: Optional async target extractor for controlled model-free runs.
    returns:
        Judgment mappings with target context and amount populated.
    """
    extractor = extract_award if extractor is None else extractor
    output = []
    for row in rows:
        if row["selection_status"] != "selected":
            output.append(dict(row))
            continue
        if row["target_json"] is not None or row["target_total_pln"] is not None:
            raise ValueError(f"Target already present for SAOS ID {row['saos_id']}")
        record = json.loads(row["selected_record_json"])
        if record["id"] != row["saos_id"] or record["text"] != row["judgment_text"]:
            raise ValueError(f"Selected record does not match source row {row['saos_id']}")
        award = await extractor(None, record["text"], [], config)
        reason = target_rejection_reason(award, config)
        output.append({**row, "target_json": json.dumps({**award, "target_reason": reason}, ensure_ascii=False, allow_nan=False),
                       "target_total_pln": Decimal(str(award["suma"])) if reason is None else None})
    return output


@step(enable_cache=False, output_materializers=ParquetMaterializer)
def find_targets_step(cases: ParquetArtifact, config_dir: str | None = None) -> ParquetArtifact:
    """Enrich an explicitly selected managed Parquet artifact with targets.

    args:
        cases: Explicitly selected collection artifact.
        config_dir: Optional existing processing YAML directory.
    returns:
        Parquet reference published through the configured artifact store.
    """
    config = load_config(config_dir)
    rows = asyncio.run(find_target_rows(read_artifact(cases), config))
    return write_artifact(rows)


@pipeline
def find_targets(artifact_id: str, config_dir: str | None = None) -> ParquetArtifact:
    """Run target extraction independently on one selected artifact version.

    args:
        artifact_id: Exact collection artifact-version UUID, never implicit latest.
        config_dir: Optional existing processing YAML directory.
    returns:
        Published target-enriched artifact output.
    """
    return find_targets_step(cases=Client().get_artifact_version(artifact_id), config_dir=config_dir)
