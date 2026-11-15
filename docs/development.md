# Development

[Back to README](../README.md)

## Package boundaries

`dataset.cli` parses arguments, delegates acquisition to `dataset.acquisition.pipeline.run`, and handles CLI exit codes.

`clients/` owns HTTP access, read-only SQLite queries and the Basal model/worker lifecycle. `storage/` owns local records, checkpoints, pending state, locality snapshots and fitted preprocessing artifacts. Court/date enrichment and admission decisions stay in the domain packages. PostgreSQL and S3 access are not implemented.

`run(config, *, extractor=None, record_source=None)` accepts keyword-only runtime dependencies for extraction and source iteration. By default it uses the existing resumable downloader and a shared Basal worker. Tests and other interfaces can supply an async extraction context and a source iterator factory without replacing imported modules. The extraction context yields a callable accepting judgment text and its identifier; the source factory accepts acquisition settings, checkpoint and run ID, and returns a closable iterator. It must preserve the downloader's durable-output/checkpoint contract when used outside tests.

These are ordinary module boundaries and explicit dependencies; no container or interface hierarchy is required.

Configuration schemas live in the owning submodule's `settings.py` and share the explicit-source `dataset.settings.Settings` policy. File loaders retain their existing interfaces; see [settings validation](configuration.md#settings-validation) for the schema map and compatibility guarantees.

## Checks

After syncing the test group:

```bash
uv run --no-sync pytest -q
```

Tests are grouped under `tests/acquisition`, `tests/clients`, `tests/storage`, `tests/extraction`, `tests/embeddings`, `tests/preprocessing` and `tests/cli`. Root fixtures share editable configuration and source payloads; component fixtures isolate acquisition output and model caches. Pytest imports tests through importlib, without adding source directories to the import path.

```bash
uv run --no-sync pytest tests/acquisition tests/storage -q
uv run --no-sync pytest tests/cli -q
uv run --no-sync pytest -m "not cuda and not mps" -q
uv run --no-sync pytest -m cuda -q
uv run --no-sync pytest -m mps -q
```

CUDA/MPS markers select small hardware checks, which skip automatically when their backend is unavailable; they do not download models. The `cpu` marker selects the corresponding CPU numeric check. Local notebook experiments live under `tests/experiments`; their tests skip when legacy inputs are absent. They retain their separate notebook-loading setup.
