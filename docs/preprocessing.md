# Preprocessing

[Back to the project overview](../README.md) · [Extraction and embeddings](extraction.md)

The Python API loads saved records and transforms numeric/categorical features and targets. It does not create splits, concatenate text embeddings, train a regressor or make compensation predictions. See [PROJECT.md](../PROJECT.md#3-vectorize-and-train) for the design contract and remaining modeling work.

## Load records

```python
from dataset.preprocessing import load_config, load_records

settings = load_config("configs/training/model_input.yaml")
data = load_records("tmp/first-run", include_targets=True)
```

[load_records()](../src/dataset/storage/records.py) returns aligned `records`, `sample_ids` and unscaled `targets` for `valid: true` cases when targets are requested. Without `include_targets=True`, it reads predictors and IDs without requiring award files. It never fits, splits or rewrites source records.

[model_input.yaml](../configs/training/model_input.yaml) contains only `feature_fields`: an ordered, nonempty list of original predictor names. Duplicates, unknown fields, labels and transformation overrides are rejected. Text selections are retained for separate embedding work; the tabular preprocessor requires at least one non-embedding predictor.

## Fixed transformations

| Field | Representation |
|---|---|
| `judgment_year` | Final two digits divided by ten: `2025 → [0.2, 0.5]`; integer years 2000–2099 |
| `injured_party_count` | Original numeric value |
| `prior_payment` | `log1p`, then training-fitted robust scaling |
| `instance`, `court_locality_size` | One-hot categories |
| Target `total` | Training-fitted robust scaling, reversible to PLN |
| `cause`, `damage`, `limitations` | Not transformed here; encoded separately by the embedding API |

Rules live in [transforms/rules.py](../src/dataset/preprocessing/transforms/rules.py), not YAML. Missing numeric values are errors; missing categories have a reserved column and unseen categories produce an all-zero block. Feature output contains finite float64 `X`, stable sample IDs, column names and half-open `field_columns` ranges.

Target scaling subtracts the training median and divides by the training interquartile range, without a logarithm. For `[100, 200, 300]`, scaled values are `[-1, 0, 1]`; inverse transformation restores PLN. Scikit-learn protects zero-range cases. Scaling does not establish feature importance.

## Fit on training data only

First create grouped train/validation/test splits upstream, keeping related judgments, appeals and duplicates together. No splitter is implemented here. The following API sketch assumes the training subset has already been selected; it is not an end-to-end runnable training script:

```python
from dataset.preprocessing import FeaturePreprocessor, TargetPreprocessor

features = FeaturePreprocessor().fit(train_records, settings)
target = TargetPreprocessor().fit(train_targets)
X_train = features.transform(train_records, train_ids)["X"]
y_train = target.transform(train_targets)

# Reuse fitted transforms on held-out rows; never fit them again here.
X_valid = features.transform(valid_records, valid_ids)["X"]
y_valid = target.transform(valid_targets)
```

Fit separately inside each cross-validation fold. Held-out rows must reuse the training categories and scaling statistics. Combining tabular `X` with separately generated text embeddings remains unimplemented; missing text placeholders should not be embedded as facts.

## Save and reuse fitted state

```python
features.save()
target.save()

features = FeaturePreprocessor.load(settings=settings)
target = TargetPreprocessor.load()
# After a future regressor produces scaled outputs:
# amounts_pln = target.inverse_transform(model_outputs)
```

Default independent artifacts, relative to the repository rather than the working directory:

```text
checkpoints/preprocessing/feature_preprocessor.pkl
checkpoints/preprocessing/target_preprocessor.pkl
```

Explicit paths are supported. Only explicit saves create artifacts; loading records or fitting does not. Predictor artifacts contain no target state, and either preprocessor can load without the other. Feature loading can verify the exact selected field order. Prediction-side feature loading needs no awards; a future regressor can use the saved target preprocessor to return outputs to PLN.

[storage/preprocessing.py](../src/dataset/storage/preprocessing.py) stores versioned fitted state and checks preprocessing/scikit-learn compatibility. Pickle files must be trusted. Version-4 artifacts from the earlier `src.dataset` namespace remain loadable; incompatible older layouts require regeneration. Original records and debug artifacts are never rewritten.
