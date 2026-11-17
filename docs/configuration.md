# Configuration

[Back to README](../README.md)

## Configs

The implemented configuration and models currently serve data scraping and extraction only. Regression training, evaluation and prediction are not implemented.

The default configuration directory is `configs/dataset/acquisition/`:

| File | Controls |
|---|---|
| `api.yaml` | Acquisition date range and page limit |
| `features.yaml` | Selected metadata/numeric predictors and text extraction questions |
| `targets.yaml` | Embedding model/revision/window, candidate keywords, similarity threshold and patterns |
| `basal.yaml` | Basal model default and extraction/review thresholds |

The effective acquisition defaults are below; runtime overrides are listed in [`.env.example`](../.env.example).

| Setting | Default | Meaning |
|---|---|---|
| `max_age_years` | `10` | Inclusive judgment-date range ending on the initial run date |
| `max_pages` | `0` | No page limit; otherwise stop at this total page position across resumes |
| `max_gib` | `0.5` | Total output-directory limit across runs; `0` disables it |
| `download_path` | `tmp/` | Output directory relative to the project root (likely to be replaced with database) |
| `debug` | `true` | Add source/model-call files and retain eligible failed attempts |
| `timeout` | `20` | HTTP connection/read timeout in seconds |

Explicit CLI arguments override only the corresponding acquisition defaults:

```bash
uv run --no-sync get-data \
  --max-age-years 5 \
  --max-pages 2 \
  --max-gib 1 \
  --download-path tmp/dataset-five-years \
  --timeout 30 \
  --no-debug
```

`--debug` enables diagnostics and `--no-debug` overrides lower-priority values. `--config-dir path/to/config` selects another directory containing all four acquisition YAML files. YAML keeps model defaults and feature settings.

### Models and devices

The current models are:

- **Remek/basal-2.0-4.5B:** extracts predictors and reviews factuality, relevance and leakage. `basal.yaml` can alternatively select the supported `Remek/basal-2.0-mini` checkpoint. Revisions are pinned in code.
- **sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2:** embeds target patterns and eligible monetary sentences to select a judgment amount sentence.

Missing model files download automatically from Hugging Face and are reused from `basal_weights/` and `embedding_weights/`. Keep these caches outside a size-limited output directory. Locality population enrichment also downloads and caches a GUGiK snapshot under `tmp/gugik/`.

Devices default to `mps`. Set `BASAL_DEVICE` and `EMBEDDING_DEVICE` in the root `.env` or process environment to use `cpu` or `cuda`. Unavailable accelerators fail before acquisition starts.

## Settings validation

Precedence: **explicit CLI → process environment → repository-root `.env` → YAML → runtime defaults**. See [`.env.example`](../.env.example) for supported keys. Changing `EMBEDDING_MODEL` also requires `EMBEDDING_REVISION`; Basal revisions remain pinned by supported model name.

Schemas live in `settings.py` under [acquisition](../src/dataset/acquisition/settings.py), [embeddings](../src/dataset/embeddings/settings.py), [extraction/model](../src/dataset/extraction/model/settings.py) and [preprocessing](../src/dataset/preprocessing/settings.py), sharing [dataset.settings.Settings](../src/dataset/settings.py).
