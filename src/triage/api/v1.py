"""Version 1 routes. A /v2 router can be added next to this one without changing /v1."""

import uuid
from typing import Annotated

import httpx
import ollama
from fastapi import APIRouter, Depends, File, Header, Response, UploadFile

from triage.api.errors import ERROR_RESPONSES, ApiError
from triage.api.security import require_api_key
from triage.config import Settings
from triage.graph import run_triage
from triage.llm import LLMProvider
from triage.rules import RoutingPolicy
from triage.schemas import TriageResult

MODEL_ERRORS = (ConnectionError, httpx.TransportError, ollama.ResponseError)


def make_router(settings: Settings, provider: LLMProvider, policy: RoutingPolicy) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["v1"])

    @router.post(
        "/triage",
        response_model=TriageResult,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(require_api_key(settings))],
        summary="Triage one claim PDF",
        description=(
            "Upload a text-based claim PDF. Returns the extracted fields, category, queue with "
            "reasons, a short summary and a per-step trace. Personal data is redacted before "
            "any model call. Send X-Request-ID to set your own request id."
        ),
    )
    def triage(
        response: Response,
        file: Annotated[UploadFile, File(description="The claim as a PDF file")],
        x_request_id: Annotated[str | None, Header()] = None,
    ) -> TriageResult:
        request_id = x_request_id or str(uuid.uuid4())
        limit = int(settings.max_upload_mb * 1024 * 1024)
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise ApiError(
                413, "file_too_large", f"the limit is {settings.max_upload_mb} MB", request_id
            )
        if not data.startswith(b"%PDF"):
            raise ApiError(415, "unsupported_media_type", "only PDF files are accepted", request_id)
        try:
            result = run_triage(data, provider, policy, request_id=request_id)
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
        response.headers["X-Request-ID"] = request_id
        return result

    return router
