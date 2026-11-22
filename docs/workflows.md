# Local workflow interfaces

Stage 2 adds an installable `saos_workflows` package beside `saos_dataset`. It provides a local inference adapter and separate recovery state, not runnable collection, target or feature pipelines. The existing `get-raw-data` and `process-data` commands and their JSON/checkpoint contracts are unchanged. No remote inference, S3 store or training is implemented.

There is no `saos_workflows` CLI or workflow-specific settings yet. Existing acquisition and extraction settings remain in `saos_dataset`; add ZenML run settings only when a runnable pipeline needs them.

`saos_dataset.storage.parquet` provides plain local Parquet read/write for caller-supplied Arrow tables. It does not require ZenML or define a judgment schema or workflow artifact materializer. Define the smallest useful judgment format alongside the first pipeline that produces it. Publication, successful-output caching and complete interrupted-run recovery belong to Stage 3; no legacy checkpoints are migrated.

For the optional local tracking server and persistent SQLite, see [local setup](../infrastructure/zenml/local/README.md). Shared hosting and the automated extraction evaluation, model training, and future feature-pipeline split are [deferred](../infrastructure/zenml/shared/README.md). Manual fixture-only ZenML checks were not judgment pipeline runs.
