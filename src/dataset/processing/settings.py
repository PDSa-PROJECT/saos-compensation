"""Independent local processing paths and operational settings."""

from pathlib import Path

from ..configuration import validate_path


def validate_settings(settings):
    """Validate processing controls without requiring download date or page settings.

    args:
        settings: Local input/output paths, debug, size limit and locality timeout.

    returns:
        None.
    """
    if not isinstance(settings, dict) or set(settings) != {"input_path", "output_path", "debug", "max_gib", "timeout"}:
        raise ValueError("process.yaml requires input_path, output_path, debug, max_gib and timeout")
    for name in ("input_path", "output_path"):
        validate_path(settings[name], name)
    source, output = Path(settings["input_path"]), Path(settings["output_path"])
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Processing input and output directories must not overlap")
    if type(settings["debug"]) is not bool:
        raise ValueError("debug must be true or false")
    if type(settings["max_gib"]) not in (int, float) or not 0 <= settings["max_gib"] < float("inf"):
        raise ValueError("max_gib must be a nonnegative finite number")
    if type(settings["timeout"]) not in (int, float) or not 0 < settings["timeout"] < float("inf"):
        raise ValueError("timeout must be a positive finite number")
