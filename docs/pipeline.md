# Pipeline

[Back to README](../README.md)

## Independent stages

`get-raw-data` downloads date-bounded SAOS judgment pages and common-court metadata. It validates the API envelope and pagination, then atomically saves complete JSON responses, including HTML and unknown fields. It does not filter cases, normalize text, join metadata, embed sentences or load Basal.

`process-data` reads a fixed local raw snapshot. It selects common-court compensation judgments, validates and joins court metadata, normalizes text, finds targets, extracts factual predictors and checks leakage. Raw JSON remains unchanged. Accepted outputs and processing progress go to a separate directory. Processing makes no SAOS requests; model/locality caches retain their existing independent download behavior.

```mermaid
flowchart TD
    A[SAOS judgment and court dumps] --> B[get-raw-data]
    B --> C[Raw JSON pages and download checkpoint]
    C --> D[process-data: local validation and selection]
    D --> E[MiniLM target selection and amount parsing]
    D --> F[Basal factual extraction and leakage checks]
    D --> G[Court and date enrichment]
    E --> H[Admission checks]
    F --> H
    G --> H
    H --> I[Separate feature and target files]
    I --> J[Processing checkpoint]
```

Each stage resumes independently. Multiple processing runs can reuse the same raw snapshot with different extraction configuration and separate output paths. Finish downloading before processing that snapshot; extending or editing raw input invalidates an existing processing checkpoint.
