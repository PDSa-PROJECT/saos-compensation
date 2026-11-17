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
│   │   └── acquisition/           # API, features, targets and Basal settings
│   └── training/                  # model input feature selection
├── src/                           # implementation
│   └── dataset/                   # dataset preparation
│       ├── cli/                   # argument parsing and acquisition entry point
│       ├── acquisition/           # resumable downloads, validation and metadata enrichment
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

For acquisition with Basal on CPU:

```bash
uv sync --locked --extra extraction --group test
```

For embeddings alone, use `uv sync --locked`. PyTorch and Transformers are base dependencies. Basal is optional: the platform extras above or the `extraction` extra install it for the full `get-data` pipeline. The test group adds pytest and may be omitted when only running acquisition. Execute subsequent commands with `uv run --no-sync` to use the installed environment without changing dependencies.

## Download and extract data

Run commands from the repository root:

```bash
uv run --no-sync get-data --help

# Small initial run: at most one dump page, containing up to 100 judgments
uv run --no-sync get-data --max-pages 1 --download-path tmp/dataset
```

The equivalent module entry point is `uv run --no-sync python -m dataset.cli`. Both use the installed `dataset` package from the `src/` layout, without modifying Python import paths.

This command downloads judgments and runs extraction. There is no download-only CLI mode. A page contains all judgment types; local filtering and extraction can leave few or no retained cases.

### Arguments

| Argument | Meaning |
|---|---|
| `-h`, `--help` | Show all command-line options and exit |
| `--config-dir PATH` | Directory containing the four acquisition YAML files; defaults to `configs/dataset/acquisition` |
| `--max-age-years N` | Include judgments from the last N years, anchored to the initial run date |
| `--max-pages N` | Maximum total dump pages across resumes; `0` reads all pages |
| `--max-gib N` | Total output-directory size limit in GiB across resumes; `0` disables it |
| `--download-path PATH` | Output directory relative to the project root |
| `--timeout SECONDS` | HTTP connection/read timeout |
| `--debug` | Add source/model-call diagnostics and retain eligible failed attempts |
| `--no-debug` | Disable debug output, overriding a true YAML default |

Explicit arguments override only their corresponding YAML settings. After setup, `uv run get-data --help` also works; the examples use `--no-sync` to keep dependency synchronization separate from execution.

## Documentation

- [How get-data pipeline works](docs/pipeline.md)
- [Configuration, models and devices](docs/configuration.md)
- [Output, admission, resume and storage limits](docs/acquisition.md)
- [Reusable embeddings](docs/embeddings.md)
- [Data scaling and normalization](docs/preprocessing.md)
- [Development and checks](docs/development.md)

## Contributing

Use Conventional Commits for new commit messages and pull request titles. See [CONTRIBUTING.md](CONTRIBUTING.md) for types, examples and breaking-change conventions.
