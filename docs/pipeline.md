# Pipeline

[Back to README](../README.md)

## How get-data pipeline works

1. Download judgments from SAOS and keep relevant compensation cases.
2. Find the awarded amount using sentence matching and monetary parsing.
3. Extract case facts and check their source support and target leakage.
4. Save accepted records and checkpoint progress for resuming later.

```mermaid
flowchart TD
    A[SAOS judgments] --> B[Select compensation cases]
    B --> C["Find award sentence (MiniLM) and parse amount"]
    B --> D["Extract case facts (BASAL)"]
    B --> E[Read court and date metadata]
    C --> F[Regression target]
    D --> G["Check source support and target leakage (BASAL)"]
    G --> H[Predictor features]
    E --> H
    F --> I[Validate dataset record]
    H --> I
    I --> J[Save target and features separately]
    J --> K[Checkpoint progress]
```
