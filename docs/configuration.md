# Configuration

[Back to README](../README.md)

## Configs

The implemented configuration and models currently serve data scraping and extraction only. Regression training, evaluation and prediction are not implemented.

The stages have separate configuration directories:

| File | Controls |
|---|---|
| `configs/dataset/acquisition/api.yaml` | Raw download dates, page/size limits, destination, console progress and HTTP timeout |
| `configs/dataset/processing/process.yaml` | Local input/output paths, processed-output size limit, debug and locality timeout |
| `configs/dataset/processing/features.yaml` | Selected metadata/numeric predictors and text extraction questions |
| `configs/dataset/processing/targets.yaml` | Embedding model/device, candidate keywords, similarity threshold and target/exclusion patterns |
| `configs/dataset/processing/basal.yaml` | Basal model/device and extraction/review thresholds |

Acquisition defaults: `max_age_years: 10`, `max_pages: 0` (unlimited), `max_gib: 0.5`, `download_path: tmp/raw`, `debug: true`, `timeout: 20`. Page limits count judgment pages across resumptions, excluding court metadata. Raw debug prints per-page progress; all raw responses are saved regardless of this flag.

Processing defaults: `input_path: tmp/raw`, `output_path: tmp/processed`, `max_gib: 0.5`, `debug: true`, `timeout: 20`. Its size budget applies only to processed output. Debug preserves source/model-call diagnostics and eligible failed target attempts. The timeout applies to locality metadata downloads, not SAOS. Input and output paths must be relative to the repository root and must not overlap, including through symlinks.

Explicit CLI arguments override only their corresponding stage defaults:

```bash
uv run --no-sync get-raw-data --max-age-years 5 --max-pages 2 --download-path tmp/raw-five-years --timeout 30 --no-debug
uv run --no-sync process-data --input-path tmp/raw-five-years --output-path tmp/processed-five-years --no-debug
```

`--config-dir` selects another directory for the invoked stage only: raw downloading needs only `api.yaml`; processing needs `process.yaml`, `features.yaml`, `targets.yaml` and `basal.yaml`. Processing has no date or page-limit flags: the saved raw snapshot defines its input. Model and feature settings are changed in YAML.

### Models and devices

The current models are:

- **Remek/basal-2.0-4.5B:** extracts predictors and reviews factuality, relevance and leakage. `basal.yaml` can alternatively select the supported `Remek/basal-2.0-mini` checkpoint. Revisions are pinned in code.
- **sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2:** embeds target patterns and eligible monetary sentences to select a judgment amount sentence.

Missing model files download automatically from Hugging Face and are reused from `basal_weights/` and `embedding_weights/`. Keep these caches outside a size-limited output directory. Locality population enrichment also downloads and caches a GUGiK snapshot under `tmp/gugik/`.

The default configuration selects `mps` in **both** `configs/dataset/processing/basal.yaml` and `configs/dataset/processing/targets.yaml`. Set both devices to `cpu` or `cuda` for another runtime. Unavailable accelerators fail before inference starts; raw downloading does not check devices.
