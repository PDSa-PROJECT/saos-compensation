# Preprocessing

[Back to README](../README.md)

## Data scaling and normalization

Feature transformations and persistence are implemented directly in `feature_preprocessor.py`; target scaling has its own `target_preprocessor.py`.

| Field | Representation |
|---|---|
| `cause`, `damage`, `limitations` | Existing text embeddings, with no additional normalization here |
| `judgment_year` | Final two digits divided by ten: `2025 → [0.2, 0.5]`; integer years 2000–2099 |
| `injured_party_count` | Original numeric value |
| `prior_payment` | `log1p`, then training-fitted robust scaling |
| `court_type`, `instance`, `court_locality_size` | One-hot category vectors |
| Target `total` | Training-fitted robust scaling, inverted to PLN for evaluation |

The preprocessing utilities use `configs/training/model_input.yaml` only to select original predictor fields. `load_records()` lives in `src/dataset/storage/records.py` and is exported from the package:

```python
from dataset.preprocessing import (
    FeaturePreprocessor, TargetPreprocessor, load_config, load_records,
)

settings = load_config("configs/training/model_input.yaml")
data = load_records("tmp/test", include_targets=True)
# data contains aligned raw records, sample_ids and unscaled targets (valid=true only).
# The caller must create grouped splits and select train_records/train_targets first.
features = FeaturePreprocessor().fit(train_records, settings)
target = TargetPreprocessor().fit(train_targets)
X_train = features.transform(train_records, train_ids)["X"]
y_train = target.transform(train_targets)
features.save()  # checkpoints/preprocessing/feature_preprocessor.pkl
target.save()    # checkpoints/preprocessing/target_preprocessor.pkl

features = FeaturePreprocessor.load(settings=settings)
target = TargetPreprocessor.load()
# target.inverse_transform(model_outputs) will recover PLN amounts.
```

This is a utility API example, not a training/inference implementation. Neither `load_records()` nor the preprocessors create splits, fit a regressor or automatically call one another. `load_records(directory)` without `include_targets` needs no award files. Future training code should call the loader before splitting and fit both preprocessors only on its training rows; future inference can reuse each saved artifact without fitting again.

`model_input.yaml` contains only `feature_fields`, an ordered list before encoding/scaling. It may select `cause`, `damage`, `limitations`, `judgment_year`, `injured_party_count`, `prior_payment`, `court_type`, `instance` and `court_locality_size`. No transformation policies are accepted. Text fields remain separate embeddings with no normalization here; the current feature preprocessor requires at least one selected tabular field.

Feature output contains finite `X`, stable IDs, column names and half-open field-to-column ranges. Fixed rules in `transforms/rules.py` are: year → final two digits divided by ten (2000–2099), count unchanged, prior payment → log1p plus training-fitted robust scaling, nominal categories → one-hot. Missing numbers raise; missing categories get a dedicated column and unseen categories an all-zero block. Target preprocessing separately subtracts the training-target median and divides by the training interquartile range, without log transformation; inverse transformation returns PLN. For [100, 200, 300], the scaled targets are [-1, 0, 1]. Zero-range protection is provided by scikit-learn. Scaling does not establish feature importance.

`preprocessing/io/` handles configuration; `storage/preprocessing.py` persists fitted state; `storage/records.py` loads dataset records; `transforms/` holds shared numeric helpers and fixed rules. Both artifacts use trusted local pickle files and reject incompatible preprocessing/scikit-learn versions. Version-4 artifacts saved with the previous `src.dataset` imports remain loadable. Feature and target files are independent, with no duplicated target object in the feature artifact. Source/debug records are unchanged. Combining tabular output with embeddings remains unimplemented.
