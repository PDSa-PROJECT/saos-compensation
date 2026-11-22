# Local judgment pipelines

`saos_workflows.pipelines` contains three independent ZenML pipelines: `collect_cases`, `find_targets` and `extract_features`. Each module owns its step and stage-specific helpers; there is no operations layer. Shared dataset logic, row schema, validation and serialization stay in `saos_dataset`. `saos_workflows.artifacts` bridges plain Parquet files to ZenML's configured artifact store without introducing separate local/S3 storage classes. Run the pipelines separately and explicitly select an upstream artifact version. Legacy commands, JSON files and checkpoints remain unchanged.

- `collect_cases(start_date, end_date, phrases, selected_phrases=None, max_records=0, timeout=30.0)` searches SAOS with one shared timed session, fetches unique full judgments up to a positive cap (0 means unlimited), joins court metadata and retains selected, filtered and rejected IDs. It does not run a model.
- `find_targets(artifact_id, config_dir=None)` selects the exact collection artifact-version UUID and runs existing embedding-based amount logic on selected cases only. Unconfirmed amounts remain null. It does not load Basal.
- `extract_features(artifact_id, config_dir=None)` selects the exact target artifact-version UUID, consumes its target context without rerunning matching and applies existing predictor/admission rules. Rejected/skipped rows remain present. Model/locality loading occurs only when needed.

Each step stages validated Parquet temporarily, then its `ParquetMaterializer` publishes the file as `data.parquet` using ZenML's `fileio.copy` with overwrite disabled. ZenML cleans staging files after step execution. Loading an artifact returns `ParquetArtifact(uri)` without reading the table. Stage execution reads the chosen input directly through an artifact-store stream, without a second temporary file; it currently processes rows in memory. PyArrow handles Parquet encoding/decoding; the core module retains only the judgment schema and validated row read/write functions. The same ZenML transport supports local and S3 storage, selected by stack configuration. S3 requires ZenML's optional S3 integration and credentials; no bucket is provisioned by pipeline code. Direct Polars S3 scans need their own runtime authentication.

The shared row layout retains complete source JSON, selection status/reason, exact decimal PLN target, target context, feature evidence/reviews and eligibility. Target/feature details remain JSON columns. No extra legacy case files are created, and no implicit latest artifact is selected.

```python
run = collect_cases(start_date="2020-01-01", end_date="2020-12-31",
                    phrases=["zadośćuczynienie"], max_records=4)
version = run.steps["collect_cases_step"].outputs["output"][0]
reference = version.load()  # URI only; suitable for a later lazy scan
target_run = find_targets(artifact_id=str(version.id))
```

Relative `config_dir`, cache paths and `.env` use the process working directory; managed output locations come from ZenML. No pipeline discovers a repository root from source. Processing `config["paths"]` supplies `MODEL_CACHE_PATH`, `ENCODER_CACHE_PATH` and `LOCALITIES_PATH` (defaults: `basal_weights`, `embedding_weights`, `tmp/gugik`).

Both workflows use `saos_dataset` for query construction (`acquisition.settings.search_query`), pagination continuation (`clients.api.has_next_page`), admission/reason composition (`extraction.quality.admission_decision`), locality initialization (`processing.localities.load_locality_context`) and model/worker lifetime (`clients.basal.open_server`). Admission distinguishes retention from validity: debug attempts can receive metadata while remaining ineligible, and missing damage still prevents legacy retention. Combined rejection reasons use the legacy “text feature extraction skipped” wording when predictors were not evaluated. Existing source, target, predictor, metadata and device checks remain shared. Legacy processing keeps page/output durability, pending state, checkpoints and locality-hash verification; the individual pipeline modules keep phrase union, record caps, stage skipping and Parquet mapping. The target-only stage continues to call the existing amount extractor, and the feature stage calls only the target-prepared predictor helper.

The local artifact store and exact-version handoffs were verified across all three decorated pipelines with fake API/model responses. Live S3 authentication/publication, live SAOS collection and real model inference remain unverified. Successful-output caching, automatic per-ID recovery and remote inference remain unimplemented. Failed publication must not be treated as a completed artifact; no custom S3 atomic-rename guarantee is introduced. Local tracking setup is documented [here](../infrastructure/zenml/local/README.md); shared hosting remains [deferred](../infrastructure/zenml/shared/README.md).

## Explore local Parquet in the browser

From the repository root, sync the optional dependencies separately. Use `edit` to change cells and save the notebook's Python source, or `run` to use the app without a code editor:

```bash
uv sync --locked --group exploration
uv run --no-sync marimo edit notebooks/explore_dataset.py
# Or, for the interactive app only:
uv run --no-sync marimo run notebooks/explore_dataset.py
```

Enter the path to one existing local judgment Parquet file (absolute or relative to the working directory). For a local ZenML output, copy the **artifact version UUID**, not the artifact name or run ID. In the same ZenML environment that produced the output, resolve that exact version without running a pipeline or loading any rows:

```python
from uuid import UUID

from zenml.client import Client

version = Client().get_artifact_version(UUID("<artifact-version-uuid>"))
print(version.load().uri)  # For these workflow outputs, the local data.parquet path.
```

Paste the path into the notebook; it does not look up versions or select the latest one. S3 paths are out of scope for this notebook.

- Click **Apply** to read the selected file and run its overview with the current filters. Selection, eligibility, amount category, and selection reason are filterable. Unset eligibility means not evaluated; a missing amount is not a zero award. Results show filtered counts, the top ten selection reasons, and up to 50 matching rows in file order (not a random sample). A new Apply clears the previous judgment lookup.
- Enter a **SAOS judgment ID** and click **Run** to inspect one row from the applied file, independently of the overview filters. This is where the notebook reads the normalized text and saved source, target, and feature JSON. Stage-specific target/feature statuses and reasons are in those JSON payloads, not scalar overview columns. Evidence and reviews retain their saved offsets and individual scores; the notebook does not compute new scores or call SAOS or a model.

The overview only projects scalar columns. For example, a bounded sample can be collected without reading judgment text or decoding JSON:

```python
import polars as pl

sample = (
    pl.scan_parquet("/path/to/data.parquet", glob=False)
    .filter(pl.col("eligible"))
    .select("saos_id", "target_total_pln")
    .limit(50)
    .collect(engine="streaming")
)
```

Streaming still retains collected results, and summary queries may scan all matching scalar values. Keep an explicit limit on review samples.
