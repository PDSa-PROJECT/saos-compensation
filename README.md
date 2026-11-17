# SAOS Compensation

## About

A study project for building a regression model that estimates compensation awarded in Polish court judgments published through SAOS.

The current implementation prepares datasets and provides preprocessing utilities. Compensation prediction is not implemented yet.

## Roadmap

- [x] Download and filter judgments from SAOS
- [x] Extract factual predictors and monetary targets
- [x] Support resumable acquisition and local storage
- [x] Provide reusable text embeddings and tabular/target preprocessing
- [ ] Implement grouped train/validation/test splits
- [ ] Combine text embeddings and tabular features
- [ ] Train and evaluate a baseline regression model
- [ ] Support YAML-configured alternative regression models
- [ ] Implement compensation prediction
- [ ] Add PostgreSQL/pgvector ingestion

Checked means implemented, not independently validated or production-ready.

## Repository structure

Tracked project directories, excluding generated outputs and model caches.

```text
saos-compensation/
├── .github/
│   └── workflows/                 # CI workflows
├── configs/                       # experiment configuration
│   ├── dataset/
│   │   ├── acquisition/           # raw SAOS download settings
│   │   └── processing/            # local processing, features, targets and Basal settings
│   └── training/                  # model input feature selection
├── src/                           # implementation
│   └── dataset/                   # dataset preparation
│       ├── cli/                   # argument parsing and two entry points
│       ├── acquisition/           # resumable raw SAOS downloads
│       ├── processing/            # local selection, validation, metadata and extraction orchestration
│       ├── extraction/            # predictor extraction and validation
│       │   ├── model/             # model configuration, prompts and decision cache
│       │   ├── source/            # source normalization and passage selection
│       │   └── targets/           # monetary parsing and prior-payment extraction
│       ├── embeddings/            # text encoding and target sentence matching
│       ├── storage/               # records, checkpoints, locality snapshots and atomic writes
│       ├── clients/               # HTTP, Basal worker and read-only SQLite integrations
│       └── preprocessing/         # numeric/category encoding and reversible target scaling
├── tests/                         # checks grouped by component, with shared fixtures
├── fixtures/                      # development snapshots
├── docs/                          # development documentation
├── data/                          # dataset placeholder
└── checkpoints/                   # model checkpoints and preprocessing/ fitted state
```

## Package boundaries

The installed package is `dataset`, discovered under `src/`. Acquisition, extraction, embeddings and preprocessing remain reusable independently of the command.

See the [development guide](docs/development.md#package-boundaries) for module responsibilities and runtime dependencies.

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). From the repository root, sync the environment for your platform:

```bash
# macOS with Apple MPS or CPU
uv sync --locked --extra pytorch-macos --group test

# Linux with NVIDIA CUDA
uv sync --locked --extra pytorch-cuda-linux --group test
```

For processing with Basal on CPU:

```bash
uv sync --locked --extra extraction --group test
```

For embeddings alone, use `uv sync --locked`. PyTorch and Transformers are base dependencies. Basal is optional: the platform extras above or the `extraction` extra install it for `process-data`. The test group adds pytest and may be omitted when not running tests. Execute subsequent commands with `uv run --no-sync` to use the installed environment without changing dependencies.

## Download and process data

Run the two independent commands from the repository root:

```bash
uv run --no-sync get-raw-data --help
uv run --no-sync process-data --help

# Download complete API responses without filtering or inference
uv run --no-sync get-raw-data --max-age-years 10 --max-gib 10 --download-path tmp/test --debug --timeout 60

# Extract features and targets from the saved JSON into a separate directory
uv run --no-sync process-data --input-path tmp/test --output-path tmp/test-processed --debug
```

For a small first download, add `--max-pages 1` (at most 100 judgments, plus court metadata). Raw downloading imports no model code and needs no Basal installation or accelerator. `uv sync --locked` is sufficient for this stage. `process-data` uses the configured models and local source files; it makes no SAOS requests. Missing model weights and the optional locality snapshot may still require network access.

The equivalent module entry points are `python -m dataset.cli` and `python -m dataset.cli.process`. The former `get-data` command is replaced by these two commands.

Dataset paths accept absolute locations, such as `process-data --input-path /tmp/raw/ --output-path /tmp/processed/`, and relative paths, including `..`. Relative paths are resolved from the project root. Processing input and output directories must not overlap, including through symlinks.

### Download arguments

| Argument | Meaning |
|---|---|
| `--config-dir PATH` | Directory containing `api.yaml`; defaults to `configs/dataset/acquisition` |
| `--max-age-years N` | Include judgments from the last N years, anchored to the initial run date |
| `--max-pages N` | Maximum total judgment dump pages across resumes; `0` reads all pages |
| `--max-gib N` | Total raw-output limit in GiB across resumes; `0` disables it |
| `--download-path PATH` | Raw output directory (absolute or relative); default `tmp/raw` |
| `--timeout SECONDS` | HTTP connection/read timeout |
| `--debug`, `--no-debug` | Enable or disable per-page console progress; raw JSON is always saved |

For `get-raw-data`, debug controls only per-page console progress. Full raw JSON responses and the download checkpoint are saved in both modes; the final console summary is also printed in both modes.

### Processing arguments

| Argument | Meaning |
|---|---|
| `--config-dir PATH` | Directory containing processing YAML files; defaults to `configs/dataset/processing` |
| `--input-path PATH` | Saved raw dataset (absolute or relative); default `tmp/raw` |
| `--output-path PATH` | Separate processed dataset (absolute or relative); default `tmp/processed` |
| `--max-gib N` | Total processed-output limit in GiB across resumes; independent of the raw limit |
| `--timeout SECONDS` | HTTP timeout for locality metadata |
| `--debug`, `--no-debug` | Enable or disable source/model-call diagnostics and eligible failed attempts |

For `process-data`, debug adds `source.txt` and `model_calls.json` to retained case folders. It can also retain completed attempts with missing or unconfirmed targets as `valid: false` in `award.json`, provided accepted source-backed `damage` evidence exists. Source and leakage checks remain active. With `--no-debug`, newly saved cases contain only `record.json` and `award.json` and must have `valid: true`; existing artifacts are preserved. Training must select `valid: true` records.

Processing checkpoints and temporary `pending/` state preserve progress and completed model decisions in both modes. Pending state is removed after acceptance or rejection. See [output and resume details](docs/acquisition.md).

Both commands support `-h`/`--help`. Explicit arguments override their corresponding environment, root `.env` and YAML values; `--no-debug` overrides a true YAML default. Model, feature and extraction settings stay in processing YAML. Use separate output directories for changed processing experiments; the same raw JSON can serve each experiment.

## Documentation

- [How the two-stage pipeline works](docs/pipeline.md)
- [Configuration, models and devices](docs/configuration.md)
- [Output, admission, resume and storage limits](docs/acquisition.md)
- [Reusable embeddings](docs/embeddings.md)
- [Data scaling and normalization](docs/preprocessing.md)
- [Development and checks](docs/development.md)

## Contributing

Use Conventional Commits for new commit messages and pull request titles. See [CONTRIBUTING.md](CONTRIBUTING.md) for types, examples and breaking-change conventions.
