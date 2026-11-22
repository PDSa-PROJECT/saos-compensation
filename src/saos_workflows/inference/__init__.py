"""Local inference boundary without model loading or cloud dependencies on import."""

from .local import LocalInferenceAdapter, open_local_inference
from .protocol import ENGINE_VERSION, InferenceIdentity, InferenceServer

__all__ = [
    "ENGINE_VERSION",
    "InferenceIdentity",
    "InferenceServer",
    "LocalInferenceAdapter",
    "open_local_inference",
]
