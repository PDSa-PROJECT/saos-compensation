"""Download-only application entry point."""

from .download import download


def run(config):
    """Acquire raw API responses independently of processing configuration and models.

    args:
        config: Validated acquisition settings.

    returns:
        None.
    """
    download(config)
