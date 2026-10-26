"""Keyless routes for the local demo page (the "backend for frontend" pattern).

The page posts the file to /demo/triage; the server runs the same TriageService as /v1, so no
API key ever reaches the browser. Without a key, the route is protected another way: it is
off unless demo_enabled, and it answers only loopback clients unless demo_local_only is off.
In a real deployment this route would sit behind a user login instead.
"""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from triage.api.errors import ApiError
from triage.api.service import TriageService
from triage.golden import GOLDEN_DIR
from triage.schemas import TriageResult

PAGE = (Path(__file__).parent / "demo.html").read_text(encoding="utf-8")
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
# Synthetic golden claims offered on the page, chosen to show the main paths.
SAMPLES = {
    "case_002": "Italian letter, kitchen fire, 83,302 euros",
    "case_013": "German claim form, storm damage",
    "case_001": "German email, small car accident",
    "case_018": "Austrian email holding two claims",
    "case_030": "Austrian letter, water or fire (ambiguous)",
    "case_007": "German form with the policy number missing",
}


def make_demo_router(service: TriageService) -> APIRouter:
    settings = service.settings
    router = APIRouter(tags=["demo"])

    def enabled() -> None:
        if not settings.demo_enabled:
            raise ApiError(404, "not_found", "the demo page is switched off")

    def local_only(request: Request) -> None:
        enabled()
        host = request.client.host if request.client else ""
        if settings.demo_local_only and host not in LOOPBACK:
            raise ApiError(
                403, "demo_local_only", "the demo answers only requests from this machine"
            )

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    def page(_: Annotated[None, Depends(enabled)]) -> str:
        return PAGE

    @router.get("/demo/samples", summary="Synthetic sample claims for the demo page")
    def samples(_: Annotated[None, Depends(local_only)]) -> list[dict[str, str]]:
        return [{"case_id": case_id, "label": label} for case_id, label in SAMPLES.items()]

    @router.get("/demo/samples/{name}", summary="Download one sample claim PDF")
    def sample_pdf(name: str, _: Annotated[None, Depends(local_only)]) -> FileResponse:
        case_id = name.removesuffix(".pdf")
        if case_id not in SAMPLES or not name.endswith(".pdf"):
            raise ApiError(404, "not_found", "unknown sample")
        return FileResponse(GOLDEN_DIR / "dev" / f"{case_id}.pdf", media_type="application/pdf")

    @router.post(
        "/demo/triage",
        response_model=TriageResult,
        summary="Triage a claim from the local demo page, without an API key",
    )
    def demo_triage(
        response: Response,
        file: Annotated[UploadFile, File(description="The claim as a PDF file")],
        _: Annotated[None, Depends(local_only)],
    ) -> TriageResult:
        request_id = str(uuid.uuid4())
        result = service.handle(file, request_id)
        response.headers["X-Request-ID"] = request_id
        return result

    return router
