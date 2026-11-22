# Embeddings

[Back to README](../README.md)

## Reusable embeddings

```python
from saos_dataset import load_config
from saos_dataset.embeddings import create_embeddings

settings = load_config()["embedding"]
vectors = create_embeddings(["Opis szkody.", "Ograniczenia w pracy."], settings)
```

`create_embeddings` accepts a nonempty list of nonblank strings and encoder settings (`model`, `revision`, `device`, `batch_size`, `max_length`). It returns an `(N, D)` float32 PyTorch tensor on the selected device, preserving order and original text through all token windows. Encoder loading is lazy and cached for unchanged settings. Target matching applies its own monetary normalization before encoding.
