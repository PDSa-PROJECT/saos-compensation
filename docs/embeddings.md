# Embeddings

[Back to README](../README.md)

## Reusable embeddings

```python
from dataset import load_config
from dataset.embeddings import create_embeddings

settings = load_config()["embedding"]
vectors = create_embeddings(["Opis szkody.", "Ograniczenia w pracy."], settings)
```

`create_embeddings` accepts a nonempty list of nonblank strings and encoder settings (`model`, `revision`, `device`, `batch_size`, `max_length`). It returns an `(N, D)` float32 PyTorch tensor on the selected device, preserving input order. Each input is encoded once, mean-pooling its token representations; text exceeding max_length tokens is truncated at the tail. Acquisition sets max_length to 512. Encoder loading is lazy and cached for unchanged settings. Target matching applies its own monetary normalization before encoding.

For denial matching, a sentence fitting the limit is encoded whole. Longer sentences use moving token windows with max_length=512 and window_overlap=256 from targets.yaml. The tokenizer includes two boundary tokens in the 512-token limit: a full window contains 510 source tokens and advances by 254, retaining 256 source tokens of overlap. The last window may be shorter; the entire sentence is covered. Windows compete independently with other candidates; their vectors and scores are never averaged. Only the strongest eligible match across the entire judgment is retained, with exact source offsets.
