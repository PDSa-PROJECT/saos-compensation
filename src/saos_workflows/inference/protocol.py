"""Minimal model identity and async request boundary shared by workflow callers."""

import re
from dataclasses import dataclass
from typing import Any, Protocol

ENGINE_VERSION = "2.4.1"


@dataclass(frozen=True)
class InferenceIdentity:
    """An immutable model snapshot and the actual supported Basal runtime."""

    model: str
    revision: str
    engine: str = "basal"
    engine_version: str = ENGINE_VERSION

    def __post_init__(self):
        """Reject mutable revisions and misleading runtime labels.

        args:
            self: Requested inference identity.
        returns:
            None.
        """
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("An explicit model identifier is required")
        if not isinstance(self.revision, str) or not re.fullmatch(r"[0-9a-f]{40}", self.revision):
            raise ValueError("Model revision must be a pinned 40-character commit hash")
        if self.engine != "basal" or self.engine_version != ENGINE_VERSION:
            raise ValueError("Local inference requires Basal engine 2.4.1")


class InferenceServer(Protocol):
    """Structural boundary compatible with the existing model decision caller."""

    identity: InferenceIdentity

    async def serve(self, request: dict[str, Any]) -> dict[str, Any]:
        """Return the validated raw response, preserving the existing envelope.

        args:
            self: Inference adapter with explicit model and engine identity.
            request: Existing Basal state/language/questions request.
        returns:
            Raw Basal response after applicable core answer validation.
        """
        ...
