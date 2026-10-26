"""Version 1 routes. A /v2 router can be added next to this one without changing /v1."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Header, Response, UploadFile

from triage.api.errors import ERROR_RESPONSES
from triage.api.security import require_api_key
from triage.api.service import TriageService
from triage.schemas import TriageResult


def make_router(service: TriageService) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["v1"])
    auth = [Depends(require_api_key(service.settings))]

    @router.get(
        "/metrics",
        dependencies=auth,
        responses={401: ERROR_RESPONSES[401]},
        summary="Request counts, error rate and latency since the server started",
    )
    def get_metrics() -> dict[str, Any]:
        return service.metrics.snapshot()

    @router.post(
        "/triage",
        response_model=TriageResult,
        responses=ERROR_RESPONSES,
        dependencies=auth,
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
        result = service.handle(file, request_id)
        response.headers["X-Request-ID"] = request_id
        return result

    return router
