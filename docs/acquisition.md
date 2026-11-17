# Acquisition

[Back to README](../README.md)

## Raw output

```text
<download_path>/
├── checkpoint.json
├── common_courts/
│   └── 00000000.json       # full original court API response per page
└── judgments/
    └── 00000000.json       # full original judgment API response per page
```

Responses retain their complete JSON structure, unknown fields and HTML text. These are API-page files, not extracted case records. No case is discarded for missing compensation evidence during downloading. Court pages are downloaded first for later local metadata joins. Raw `--debug` controls only per-page console progress; `--no-debug` still saves the same raw JSON and checkpoint and prints the final summary.

## Processed output and admission

```text
<output_path>/
├── checkpoint.json
└── <SAOS_ID>/
    ├── record.json         # selected predictor values only
    ├── award.json          # total and valid only
    ├── source.txt          # processing debug=true only
    └── model_calls.json    # processing debug=true only
```

Processing selects common-court sentences containing compensation terminology and numeric PLN evidence, deduplicates stable SAOS IDs, joins saved court metadata and validates admitted judgments. Its output and checkpoint are independent of the raw directory. Extraction/admission rules are unchanged by the stage split.

Before monetary target selection, every full sentence is compared with the 12 `judgment-denial` patterns, including sentences without PLN amounts or role keywords. A cosine match strictly above the configured threshold (default 0.7) establishes a confirmed zero-valued target only when it also exceeds the best procedural-cost match for that sentence. Cost matches win exact ties. Monetary award parsing is skipped, while factual predictors and metadata are extracted and validated normally. If no denial matches, monetary selection proceeds normally.

`award.json` contains the one regression target `total` in PLN and the boolean `valid`. Normal output requires an admissible target and an accepted source-backed `damage` description (szkoda). Other text fields may remain missing. Debug can retain completed attempts with an unresolved target as `valid: false`, provided accepted damage evidence exists. Cases without accepted damage evidence are discarded even under debug. Missing judgment matches skip text-feature inference unless a denial established a zero target. Source and leakage checks remain active for populated text fields. Training must filter for `valid: true` and independently assess label quality.

`procedural_costs` includes mutual settlement and cost offset patterns, with `rozlicz` and `potrąc` keyword stems. Excluding such a payment does not establish a denial or a zero target; a separate eligible award may still be selected.

Processing debug adds only `source.txt` and `model_calls.json` to retained case folders; evidence and confidence diagnostics stay out of the two basic files. With `--no-debug`, newly saved cases contain only `record.json` and `award.json` and must have `valid: true`. Checkpoints and temporary pending state are maintained in either mode. Rejected cases leave no final case files. Existing artifacts are preserved, so use a fresh output path for a clean dataset layout. Operational summaries are printed to the console.

## Resume and storage limits

Restart the same stage command after interruption. Raw `checkpoint.json` pins the dataset ID and original date bounds and records independent court/judgment page cursors. Each raw page becomes durable before its cursor advances. A saved page left behind by an interrupted checkpoint write is reused without another HTTP request. Debug, timeout, size and page limits may change; increasing the page limit continues downloading. Changing the age range requires a new download path. A completed download performs no more requests.

The processing checkpoint pins extraction configuration, raw content signature, locality snapshot hash and the next page/item. Final case files become durable before processing advances. Saved records are recognized without repeated extraction. Temporary `<SAOS_ID>/pending/` state retains source/configuration and completed model decisions independently of debug; it is removed after acceptance or rejection. Rejecting a case never deletes its raw input.

Finish raw downloading before processing the saved snapshot. A page-limited raw dataset can be processed even if more pages exist remotely. Extending or editing raw input requires a new processing output path. Models, patterns and questions must remain compatible with the processing checkpoint; changed experiments or legacy combined-pipeline artifacts require a separate destination. The extractor remains version **31**. Processing debug, timeout and size limits may change during a resume. Run one process per output directory.

Each stage enforces its own `max_gib` against all files in its output directory, including existing files and atomic temporary writes; processing also counts pending/debug files. A refused write leaves resumable progress; increase the corresponding limit to continue. Existing artifacts are preserved, and neither stage adopts an unrelated or legacy checkpoint. Input/output directories must not overlap. Model caches stay outside size-limited processed output. A page limit follows dump order and is not random sampling.
