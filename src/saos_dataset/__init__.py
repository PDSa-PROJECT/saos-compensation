"""Independent raw acquisition, extraction and preprocessing APIs."""

from importlib import import_module

__all__ = ["extract", "extract_text", "load_config"]


def __getattr__(name):
    """Load optional extraction APIs only when requested by their callers.

    args:
        name: Public extraction attribute.

    returns:
        Requested function without loading models for raw-download imports.
    """
    modules = {"extract": ".extraction.basal_filtering", "extract_text": ".extraction.source.text",
               "load_config": ".extraction.model.configuration"}
    if name not in modules:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(modules[name], __name__), name)
