"""Native Basal adapter reusing the core snapshot and worker lifecycle."""

from contextlib import asynccontextmanager
from copy import deepcopy
from importlib.metadata import version

from saos_dataset.clients.basal import create_server, load_model, open_worker
from saos_dataset.extraction.model.decisions import check_decision
from saos_dataset.extraction.model.settings import MODEL_REVISIONS

from .protocol import ENGINE_VERSION, InferenceIdentity


class LocalInferenceAdapter:
    """Validate responses without changing the legacy server request or result."""

    def __init__(self, server, identity):
        """Bind a running server to its explicit snapshot identity.

        args:
            self: Adapter being initialized.
            server: Running server exposing async serve.
            identity: Validated identity of the loaded model and runtime.
        returns:
            None.
        """
        if not isinstance(identity, InferenceIdentity):
            raise TypeError("identity must be an InferenceIdentity")
        self.identity = identity
        self._server = server

    async def serve(self, request):
        """Preserve the serve seam and reject malformed or truncated responses.

        args:
            self: Adapter bound to the running local worker.
            request: Basal request, optionally including questions and source state.
        returns:
            Original validated response envelope, not just its answers.
        """
        if not isinstance(request, dict):
            raise ValueError("Inference request must be an object")
        if "questions" in request and not isinstance(request["questions"], dict):
            raise ValueError("Inference questions must be an object")
        response = await self._server.serve(request)
        if not isinstance(response, dict):
            raise ValueError("Inference response must be an object")
        if response.get("truncated"):
            raise ValueError("The inference engine truncated its input")
        if "questions" in request:
            check_decision(response, request["questions"], request.get("state"))
        return response


@asynccontextmanager
async def open_local_inference(model, cache, *, model_loader=None, server_factory=None):
    """Load an explicit supported snapshot only when entering the native context.

    args:
        model: Effective core model settings, including explicit pinned revision.
        cache: External model weight cache, separate from workflow recovery state.
        model_loader: Optional fake snapshot loader for offline tests.
        server_factory: Optional fake server factory; bypasses installed runtime checks.
    returns:
        Async context yielding an adapter while the shared core worker is alive.
    """
    model = deepcopy(model)
    identity = InferenceIdentity(model=model.get("model"), revision=model.get("revision"))
    if MODEL_REVISIONS.get(identity.model) != identity.revision:
        raise ValueError("Local inference requires a supported pinned model snapshot")
    if server_factory is None:
        if version("basal") != ENGINE_VERSION:
            raise ValueError("Installed Basal engine must be exactly 2.4.1")
        from saos_dataset.processing.pipeline import check_device

        check_device(model["device"])
    loader = load_model if model_loader is None else model_loader
    factory = create_server if server_factory is None else server_factory
    server = factory(model, loader(model, cache))
    async with open_worker(server):
        yield LocalInferenceAdapter(server, identity)
