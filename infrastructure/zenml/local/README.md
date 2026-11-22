# Local ZenML tracking

ZenML 0.99.0 runs the pipeline process on the Mac; `zenml[server]` adds the optional local browser dashboard backed by SQLite. Keep local metadata and artifacts outside the repository source and out of Git. From the repository root, after a separate `uv sync --locked --group test --extra pytorch-macos`:

```sh
export ZENML_CONFIG_PATH="$PWD/tmp/zenml/config"
uv run --no-sync zenml init
uv run --no-sync zenml status
uv run --no-sync zenml login --local
```

Use `uv run --no-sync zenml logout --local` to stop the dashboard. `zenml init` creates ignored `.zen/`; the ZenML configuration, SQLite database and default local artifact store persist under the ignored `tmp/zenml/` directory when the same `ZENML_CONFIG_PATH` is reused. Starting the dashboard does not start a judgment pipeline. Keep the local orchestrator; workflow Parquet files use explicit local paths rather than ZenML-managed file artifacts. S3 storage is deferred. Do not commit `tmp/zenml/` or a global ZenML configuration. On Apple Silicon, if the local server fails while forking, consult ZenML's documented `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` setting rather than changing model inference settings.
