# SAOS Compensation

A study project for estimating compensation awarded in Polish court judgments. Currently, it downloads judgments from SAOS, extracts factual predictors and monetary targets, and saves a dataset for review. Numeric/categorical preprocessing is available as a Python API.

**Compensation prediction, regression training and evaluation are not implemented yet.** Extracted records need independent label and leakage review before training. PostgreSQL/pgvector ingestion and combined text/tabular inputs are also planned.

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). Run from the repository root:

```bash
# macOS; see the acquisition guide for CPU/Linux setup
uv sync --locked --extra pytorch-macos --group test
uv run --no-sync get-data --help
uv run --no-sync get-data --max-pages 1 --download-path tmp/first-run --debug
```

The committed configuration uses MPS for both models. Check the model/device settings before running; first use downloads model weights and locality data. One page contains up to 100 judgments and may produce few or no retained cases. There is no download-only CLI mode. Use a fresh output path for a new extraction experiment.

## Output

```text
tmp/first-run/
├── checkpoint.json
└── <SAOS_ID>/
    ├── record.json         # factual predictors
    ├── award.json          # total in PLN and valid flag
    ├── source.txt          # debug only
    └── model_calls.json    # debug only
```

Inspect a completed case by comparing the source, extracted facts and award. Debug records with `valid: false` are not usable training labels; `valid: true` still requires independent quality review.

## Documentation

- [Acquisition](docs/acquisition.md) — setup, CLI, configuration, output, resume and limits.
- [Extraction](docs/extraction.md) — MiniLM, Basal, targets, predictors and leakage checks.
- [Preprocessing](docs/preprocessing.md) — record loading, transformations and fitted artifacts.
- [Development](docs/development.md) — source layout, module boundaries, tests and CI.

For the authoritative design contract, see [PROJECT.md](PROJECT.md). Progress and remaining work are recorded in [STATUS.md](STATUS.md).

## Contributing

Use Conventional Commits for commit messages and PR titles. See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution policy and [AGENTS.md](AGENTS.md) for engineering instructions.
