# Development

[Back to the project overview](../README.md) · [Contribution policy](../CONTRIBUTING.md)

Use [AGENTS.md](../AGENTS.md) for engineering instructions, [PROJECT.md](../PROJECT.md) for the authoritative design contract and [STATUS.md](../STATUS.md) for progress. This guide maps the implementation and explains checks; it does not replace those documents.

## Source layout

The installed Python package is `dataset`, discovered under `src/`:

```text
src/dataset/
├── cli/                   # CLI arguments and entry point
├── acquisition/           # orchestration, resumable downloads, validation, metadata
├── clients/               # SAOS HTTP, Basal lifecycle, read-only SQLite access
├── extraction/
│   ├── model/             # configuration, prompts, model decisions and cache
│   ├── source/            # text normalization and passage selection
│   └── targets/           # monetary parsing and earlier-payment extraction
├── embeddings/            # reusable encoding and target matching
├── storage/               # records, checkpoints, localities, atomic writes, fitted state
└── preprocessing/         # tabular encoding and reversible target scaling
```

Other useful directories:
- `configs/` — acquisition and model-input YAML.
- `tests/` — component tests and shared fixtures.
- `fixtures/` — development snapshots.
- `data/` and `checkpoints/` — dataset/checkpoint placeholders and fitted artifacts.
- `basal_weights/`, `embedding_weights/` — ignored model caches.
- `tmp/` — local acquisition outputs and the locality cache.

Local notebook experiments are ignored and may be absent. Regression architectures, training, evaluation, prediction, PostgreSQL/pgvector ingestion and S3 access are not implemented; do not treat them as existing modules.

## Follow one run through the code

1. [cli/main.py](../src/dataset/cli/main.py) parses arguments and calls the configuration loader.
2. [extraction/model/configuration.py](../src/dataset/extraction/model/configuration.py) reads the four acquisition files, applies acquisition overrides, validates values and assembles the runtime dictionary. Validation also lives in acquisition, embeddings and preprocessing; typed settings refactoring is not implemented yet.
3. [acquisition/pipeline.py](../src/dataset/acquisition/pipeline.py) manages the output budget, checkpoint, devices, locality data and shared extractor.
4. [acquisition/download.py](../src/dataset/acquisition/download.py) uses [clients/api.py](../src/dataset/clients/api.py) to obtain judgments, validate/filter them and resume pagination.
5. [extraction/basal_filtering.py](../src/dataset/extraction/basal_filtering.py) coordinates target and factual-feature extraction. See the [extraction guide](extraction.md) for MiniLM/Basal responsibilities.
6. [storage/records.py](../src/dataset/storage/records.py) writes predictors/targets; [storage/checkpoints.py](../src/dataset/storage/checkpoints.py) advances durable progress. Metadata enrichment remains in acquisition, not storage.

`clients/` owns integrations, `storage/` owns persistence and domain packages own admission/enrichment. The code uses ordinary module boundaries rather than a dependency-injection framework.

`run(config, *, extractor=None, record_source=None)` supports test/runtime dependencies. The extractor is an async context yielding a text/identifier callable; the source factory accepts acquisition settings, checkpoint and run ID and returns a closable iterator. Production replacements must preserve durable-output/checkpoint ordering. Default execution uses the resumable downloader and shared Basal worker.

## Run checks

For tests and lint without Basal inference, sync the test group; for local acquisition/model work use the appropriate [platform setup](acquisition.md#setup):

```bash
uv sync --locked --group test
uv run --no-sync ruff check src
uv run --no-sync pytest -q
```

Focused checks:

```bash
uv run --no-sync pytest tests/acquisition tests/storage -q
uv run --no-sync pytest tests/cli -q
uv run --no-sync pytest tests/embeddings tests/extraction -q
uv run --no-sync pytest tests/preprocessing -q
uv run --no-sync pytest -m "not cuda and not mps" -q
uv run --no-sync pytest -m cuda -q
uv run --no-sync pytest -m mps -q
```

Tests cover controlled behavior and boundaries, not a measured extraction-accuracy benchmark. Root fixtures share configuration/source inputs; component fixtures isolate outputs and caches. Pytest uses importlib mode without source-path injection. CPU/CUDA/MPS markers select small numeric checks that do not download models; unavailable accelerators skip. Optional historical/notebook checks skip when local inputs are absent.

## GitHub checks

| Check | Scope |
|---|---|
| `Python lint` | Ruff E4/E7/E9/F checks on `src/`, without formatting enforcement |
| `Python tests` | Full pytest suite |
| `PR title` | Conventional Commit title syntax and allowed types |

The [lint](../.github/workflows/lint.yml) and [test](../.github/workflows/tests.yml) workflows use Python 3.12 and locked uv dependencies for PRs to main, pushes to main and merge groups. The [title workflow](../.github/workflows/pr-title.yml) covers all PR bases, including stacked PRs, and runs on creation, edits, reopening, new commits and ready-for-review events. It reads event data without checking out PR code.

Title rules and squash guidance live in [CONTRIBUTING.md](../CONTRIBUTING.md). Workflows alone do not block merging: required-check protection is a separate GitHub setting. This documentation does not enable it.
