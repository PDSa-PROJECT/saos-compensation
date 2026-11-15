# Acquisition

[Back to the project overview](../README.md) · [How extraction works](extraction.md)

The `get-data` command downloads date-bounded judgments from the official SAOS dump API, filters compensation cases locally, runs extraction and saves retained cases. It is not a download-only command. The authoritative acquisition contract is in [PROJECT.md](../PROJECT.md#1-acquire-judgments-and-produce-reviewable-records).

## Setup

Use Python 3.12 and uv. From the repository root, choose one dependency setup:

```bash
# macOS, MPS or CPU
uv sync --locked --extra pytorch-macos --group test

# Linux with NVIDIA CUDA
uv sync --locked --extra pytorch-cuda-linux --group test

# CPU acquisition, without a platform extra
uv sync --locked --extra extraction --group test
```

For embeddings alone, `uv sync --locked` is sufficient: PyTorch and Transformers are base dependencies. Basal is optional and is installed by the extraction/platform extras. The test group adds development/test tools and can be omitted for acquisition alone. Keep dependency synchronization separate from execution with `uv run --no-sync`.

## Models and devices

The committed [Basal configuration](../configs/dataset/acquisition/basal.yaml) selects `Remek/basal-2.0-4.5B`; `Remek/basal-2.0-mini` is also supported. Revisions are pinned in code. [Target matching](../configs/dataset/acquisition/targets.yaml) uses `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.

Both configurations select `mps`. For CPU or CUDA, set `device` in **both** files accordingly. The requested accelerators must be available before acquisition starts; installing an extra does not change the YAML device selection.

Missing weights download from Hugging Face into `basal_weights/` and `embedding_weights/`, then are reused. Keep both caches outside a size-limited output directory. Court-locality enrichment also downloads and caches a GUGiK snapshot under `tmp/gugik/`. AWS and a database are not needed for local acquisition.

## Run a bounded acquisition

```bash
uv run --no-sync get-data --help
uv run --no-sync get-data --max-pages 1 --download-path tmp/first-run --debug
```

The equivalent entry point is `uv run --no-sync python -m dataset.cli`. A page contains up to 100 judgments of different types. Local filtering and admission checks may leave few or no retained cases; the page limit is not a sample size or random sampling method.

## Configuration and CLI overrides

The default configuration directory is `configs/dataset/acquisition/`:

| File | Controls |
|---|---|
| [api.yaml](../configs/dataset/acquisition/api.yaml) | Dates, page/size limits, output path, debug and HTTP timeout |
| [features.yaml](../configs/dataset/acquisition/features.yaml) | Selected metadata/numeric predictors and text questions |
| [targets.yaml](../configs/dataset/acquisition/targets.yaml) | Encoder/device, role keywords, similarity threshold and patterns |
| [basal.yaml](../configs/dataset/acquisition/basal.yaml) | Basal model/device and extraction/review thresholds |

| Argument | Meaning | Committed default |
|---|---|---|
| `--config-dir PATH` | Directory containing all four files | `configs/dataset/acquisition` |
| `--max-age-years N` | Inclusive judgment-date range ending on the initial run date | `10` |
| `--max-pages N` | Maximum total dump pages across resumes; `0` is unlimited | `0` |
| `--max-gib N` | Total output-directory limit across resumes; `0` disables it | `0.5` |
| `--download-path PATH` | Output directory relative to the project root | `tmp/` |
| `--timeout SECONDS` | HTTP connection/read timeout, not a total run deadline | `20` |
| `--debug` / `--no-debug` | Enable/disable diagnostics and eligible invalid attempts | `true` |
| `-h`, `--help` | Show options and exit | — |

Explicit CLI arguments override only their corresponding acquisition values. In particular, `--no-debug` overrides a true YAML setting. Change model and feature settings in YAML; use `--config-dir` for a separate configuration folder.

```bash
uv run --no-sync get-data \
  --max-age-years 5 \
  --max-pages 2 \
  --max-gib 1 \
  --download-path tmp/dataset-five-years \
  --timeout 30 \
  --no-debug
```

## Output and admission

```text
<download_path>/
├── checkpoint.json
└── <SAOS_ID>/
    ├── record.json         # selected predictor values only
    ├── award.json          # total and valid only
    ├── source.txt          # debug only
    └── model_calls.json    # debug only
```

Normal records require an admissible target and accepted source-backed `damage` evidence. Other text features may be missing. Debug may retain completed attempts with unresolved targets as `valid: false`, but does not bypass damage, source or leakage checks. Rejected cases leave no final case files; existing artifacts are not automatically removed. See [extraction](extraction.md) for the target and feature rules.

Debug adds only the source and model-call files; confidence and evidence diagnostics do not enter the two basic files. Summaries are console-only. Use `valid: true` records for label-bearing loading, followed by independent quality review.

## Resume and storage limits

Rerun the same command after interruption. `checkpoint.json` pins the original date bounds, extraction configuration and locality-snapshot hash, and records the next page/item. Completed records are recognized. Temporary `<SAOS_ID>/pending/` state preserves source/configuration and completed model decisions even without debug; it is removed after acceptance or rejection. Final records are made durable before checkpoint progress advances.

Use a new output path when models, patterns, questions or other extraction settings change, or when an older extractor version is incompatible. Debug, timeout, size and page limits may change during resume. Increasing the page limit continues acquisition; a completed dataset checkpoint does no further work. Run one process per output directory. The extraction version and compatibility contract are maintained in [PROJECT.md](../PROJECT.md), with the version defined in [prompts.py](../src/dataset/extraction/model/prompts.py).

`max_gib` includes all existing output, debug history, pending state and atomic temporary writes across resumes. The pipeline refuses writes exceeding the budget; increase the limit to continue. Model caches must remain outside the limited directory.

HTTP access uses explicit timeouts and a shared session, without automatic retry loops. A `ReadTimeout` means the remote server did not respond in time, not that model inference failed. Rerun with the same output path and, if appropriate, a larger `--timeout`; continued failures may mean the external service is unavailable.
