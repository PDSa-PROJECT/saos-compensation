# Development

[Back to README](../README.md)

## Package boundaries

`dataset.cli` parses arguments, delegates acquisition to `dataset.acquisition.pipeline.run`, and handles CLI exit codes.

`clients/` owns HTTP access, read-only SQLite queries and the Basal model/worker lifecycle. `storage/` owns local records, checkpoints, pending state, locality snapshots and fitted preprocessing artifacts. Court/date enrichment and admission decisions stay in the domain packages. PostgreSQL and S3 access are not implemented.

`run(config, *, extractor=None, record_source=None)` accepts keyword-only runtime dependencies for extraction and source iteration. By default it uses the existing resumable downloader and a shared Basal worker. Tests and other interfaces can supply an async extraction context and a source iterator factory without replacing imported modules. The extraction context yields a callable accepting judgment text and its identifier; the source factory accepts acquisition settings, checkpoint and run ID, and returns a closable iterator. It must preserve the downloader's durable-output/checkpoint contract when used outside tests.

These are ordinary module boundaries and explicit dependencies; no container or interface hierarchy is required.
