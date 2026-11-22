# Local judgment pipelines

`saos_workflows.pipelines` contains three independent ZenML pipelines: `collect_cases`, `find_targets` and `extract_features`. Each module owns its step and stage-specific helpers; there is no operations layer. Shared dataset logic, row schema, validation and serialization stay in `saos_dataset`. `saos_workflows.artifacts` bridges plain Parquet files to ZenML's configured artifact store without introducing separate local/S3 storage classes. Run the pipelines separately and explicitly select an upstream artifact version. Legacy commands, JSON files and checkpoints remain unchanged.

- `collect_cases(start_date, end_date, phrases, selected_phrases=None, max_records=0, timeout=30.0)` searches SAOS with one shared timed session, fetches unique full judgments up to a positive cap (0 means unlimited), joins court metadata and retains selected, filtered and rejected IDs. It does not run a model.
- `find_targets(artifact_id, config_dir=None)` selects the exact collection artifact-version UUID and runs existing embedding-based amount logic on selected cases only. Unconfirmed amounts remain null. It does not load Basal.
- `extract_features(artifact_id, config_dir=None)` selects the exact target artifact-version UUID, consumes its target context without rerunning matching and applies existing predictor/admission rules. Rejected/skipped rows remain present. Model/locality loading occurs only when needed.

Each step stages validated Parquet temporarily, then its `ParquetMaterializer` copies the actual file into the configured ZenML artifact store as `data.parquet`. ZenML cleans staging files after step execution. Loading an artifact returns `ParquetArtifact(uri)` without reading the table. Stage execution explicitly downloads/reads the chosen input; it currently processes rows in memory. The same store API supports local and S3 storage, selected by stack configuration. S3 requires ZenML's optional S3 integration and credentials; no bucket is provisioned by pipeline code. Direct Polars S3 scans need their own runtime authentication.

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
