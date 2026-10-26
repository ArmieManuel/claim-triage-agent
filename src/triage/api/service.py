"""Upload handling shared by /v1/triage (API key) and /demo/triage (local demo page)."""

import time

import httpx
import ollama
from fastapi import UploadFile

from triage.api.errors import ApiError
from triage.config import Settings
from triage.graph import run_triage
from triage.llm import LLMProvider
from triage.observability import Metrics
from triage.rules import RoutingPolicy
from triage.schemas import TriageResult

MODEL_ERRORS = (ConnectionError, httpx.TransportError, ollama.ResponseError)


class TriageService:
    def __init__(
        self, settings: Settings, provider: LLMProvider, policy: RoutingPolicy, metrics: Metrics
    ):
        self.settings = settings
        self.provider = provider
        self.policy = policy
        self.metrics = metrics

    def handle(self, file: UploadFile, request_id: str) -> TriageResult:
        """Check the upload, run the agent, record metrics. Raises ApiError on any failure."""
        started = time.perf_counter()
        try:
            result = self._run(file, request_id)
        except ApiError as error:
            self.metrics.record_triage_error(error.body.error)
            raise
        self.metrics.record_triage(result, time.perf_counter() - started)
        return result

    def _run(self, file: UploadFile, request_id: str) -> TriageResult:
        limit = int(self.settings.max_upload_mb * 1024 * 1024)
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise ApiError(
                413, "file_too_large", f"the limit is {self.settings.max_upload_mb} MB", request_id
            )
        if not data.startswith(b"%PDF"):
            raise ApiError(415, "unsupported_media_type", "only PDF files are accepted", request_id)
        try:
            result = run_triage(data, self.provider, self.policy, request_id=request_id)
        except MODEL_ERRORS as error:
            raise ApiError(
                503,
                "model_unavailable",
                f"the language model is not reachable, check that Ollama is running ({error})",
                request_id,
            ) from error
        if result.status == "rejected":
            raise ApiError(
                422,
                "unreadable_document",
                f"the PDF could not be read: {result.rejection_reason}",
                request_id,
            )
        return result
