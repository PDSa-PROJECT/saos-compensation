# Development

[Back to README](../README.md)

## Package boundaries

`dataset.cli.main` parses raw-download arguments and delegates to synchronous `dataset.acquisition.pipeline.run`. `dataset.cli.process` parses processing arguments and delegates to asynchronous `dataset.processing.pipeline.run`. CLI modules own parsing and exit codes, not business logic.

`clients/` owns HTTP access, read-only SQLite queries and the Basal model/worker lifecycle. `storage/` owns local records, checkpoints, pending state, locality snapshots and fitted preprocessing artifacts. `acquisition/` owns raw download settings and durable pagination. `processing/source.py` selects and validates local cases and joins saved metadata; `processing/metadata.py` enriches predictors, and `processing/pipeline.py` coordinates extraction/admission. `storage/raw.py` owns raw page persistence and snapshot identity. PostgreSQL and S3 access are not implemented.

Processing `run(config, *, extractor=None, record_source=None)` accepts keyword-only runtime dependencies for extraction and source iteration. By default it uses the resumable local raw source and a shared Basal worker. Tests and other interfaces can supply an async extraction context and a source iterator factory without replacing imported modules. The extraction context yields a callable accepting judgment text and its identifier; the source factory accepts processing settings, checkpoint and run ID, and returns a closable iterator. It must preserve the local source's durable-output/checkpoint contract when used outside tests.

These are ordinary module boundaries and explicit dependencies; no container or interface hierarchy is required.

## Installed commands

`pyproject.toml` registers `get-raw-data = "dataset.cli.main:main"` and `process-data = "dataset.cli.process:main"`. After switching branches that change these entry points, repeat the platform-specific `uv sync --locked` command from [Setup](../README.md#setup). `uv run --no-sync` uses the existing installation and does not regenerate console scripts.

The current src layout generates package metadata under `src/`. Obsolete root-level `saos_compensation.egg-info` from earlier installs can shadow the installed entry-point metadata; preserve that old directory outside the checkout before inspecting the refreshed installation.

## Checks

After syncing the test group:

```bash
uv run --no-sync pytest -q
```

Tests are grouped under `tests/acquisition`, `tests/processing`, `tests/clients`, `tests/storage`, `tests/extraction`, `tests/embeddings`, `tests/preprocessing` and `tests/cli`. Root fixtures share editable configuration and source payloads; component fixtures isolate raw/processing output and model caches. Pytest imports tests through importlib, without adding source directories to the import path.

```bash
uv run --no-sync pytest tests/acquisition tests/processing tests/storage -q
uv run --no-sync pytest tests/cli -q
uv run --no-sync pytest -m "not cuda and not mps" -q
uv run --no-sync pytest -m cuda -q
uv run --no-sync pytest -m mps -q
```

CUDA/MPS markers select small hardware checks, which skip automatically when their backend is unavailable; they do not download models. The `cpu` marker selects the corresponding CPU numeric check. Local notebook experiments live under `tests/experiments`; their tests skip when legacy inputs are absent. They retain their separate notebook-loading setup.

Raw acquisition tests mock only HTTP boundaries and cover full-payload preservation, page durability, resume and size limits. Local-source tests cover filtering, metadata joins, deduplication, unchanged raw files and processing checkpoint compatibility. CLI tests verify independent configuration and that importing the downloader does not import model code. Existing extraction tests run independently of SAOS.
