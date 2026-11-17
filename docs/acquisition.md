# Acquisition

[Back to README](../README.md)

## Output and admission

```text
<download_path>/
├── checkpoint.json
└── <SAOS_ID>/
    ├── record.json         # selected predictor values only
    ├── award.json          # total and valid only
    ├── source.txt          # debug=true only
    └── model_calls.json    # debug=true only
```

Before monetary target selection, every full sentence is compared with the configured `judgment-denial` patterns, including sentences without PLN amounts or role keywords. A cosine match strictly above `embedding.denial_minimum_cosine_similarity` (default 0.85) establishes a confirmed zero-valued target only when it also exceeds the best procedural-cost match for that sentence. Cost matches win exact ties. Sentences fitting 512 tokens are encoded whole. Longer denial sentences supply independent beginning and ending views, without averaging their embeddings or scores. All batches are scanned; only the strongest eligible denial across the entire judgment is retained, with the first source sentence winning equal denial scores. Monetary award parsing is skipped, while factual predictors and metadata are extracted and validated normally. If no denial matches, monetary selection proceeds with its independent `embedding.minimum_cosine_similarity` threshold (default 0.7).

`award.json` contains the one regression target `total` in PLN and the boolean `valid`. Normal output requires an admissible target and an accepted source-backed `damage` description (szkoda). Other text fields may remain missing. Debug can retain completed attempts with an unresolved target as `valid: false`, provided accepted damage evidence exists. Cases without accepted damage evidence are discarded even under debug. Text-feature inference runs even without a judgment match; final admission checks the target and mandatory damage evidence independently. Source and leakage checks remain active for populated text fields. Training must filter for `valid: true` and independently assess label quality.

`procedural_costs` includes mutual settlement and cost offset patterns, with `rozlicz` and `potrąc` keyword stems. Excluding such a payment does not establish a denial or a zero target; a separate eligible award may still be selected.

Debug adds only `source.txt` and `model_calls.json`; evidence and confidence diagnostics stay out of the two basic files. Rejected cases leave no final case files. Existing artifacts are preserved, so use a fresh output path for a clean dataset layout. Operational summaries are printed to the console.

## Resume and storage limits

Restart the same command after interruption. `checkpoint.json` pins the original date bounds, extraction configuration and locality snapshot hash, and records the next page/item. Saved records are recognized without repeating extraction. Temporary `<SAOS_ID>/pending/` state preserves source/configuration and completed model decisions even with debug disabled; it is removed after acceptance or rejection.

Dates, models, patterns, questions and extraction settings must remain compatible with the checkpoint. Use a new output path for a changed experiment or an older extractor version. The current extractor version is **33**. Debug, timeout, size and page limits may change during a resume; increasing the page limit continues acquisition. A fully completed checkpoint performs no further acquisition. Run one process per output directory.

`max_gib` includes existing output, debug files, pending state and atomic temporary writes across resumptions. A refused write stops the run with a resumable checkpoint; increase the limit to continue. A page limit follows dump order and is not random sampling.
