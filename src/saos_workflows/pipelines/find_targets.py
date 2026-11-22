"""Apply existing target extraction to source-backed local judgment rows."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path

from zenml import pipeline, step

from saos_dataset.extraction.model.configuration import load_config
from saos_dataset.extraction.quality import target_rejection_reason
from saos_dataset.extraction.targets.amounts import extract_award

from saos_dataset.storage.parquet import read_rows, write_rows


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


@step(enable_cache=False)
def find_targets_step(input_path: str, output_path: str, config_dir: str | None = None) -> str:
    """Enrich an explicit local Parquet file with monetary target results.

    args:
        input_path: Explicit existing local Parquet input.
        output_path: Explicit new local Parquet output.
        config_dir: Optional existing processing YAML directory.
    returns:
        Path of the completed output file.
    """
    source, destination = Path(input_path).resolve(), Path(output_path).resolve()
    if source == destination:
        raise ValueError("Target output must differ from its input")
    if destination.exists():
        raise FileExistsError(destination)
    config = load_config(config_dir)
    rows = asyncio.run(find_target_rows(read_rows(source), config))
    write_rows(destination, rows)
    return str(destination)


@pipeline
def find_targets(input_path: str, output_path: str, config_dir: str | None = None) -> str:
    """Run target extraction independently on one selected local artifact.

    args:
        input_path: Explicit source Parquet path.
        output_path: Explicit new Parquet path.
        config_dir: Optional existing processing YAML directory.
    returns:
        Path of the published target-enriched artifact.
    """
    return find_targets_step(input_path=input_path, output_path=output_path, config_dir=config_dir)
