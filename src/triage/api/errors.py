"""One error shape for every failure, with a stable machine-readable code."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    message: str
    request_id: str | None = None


class ApiError(Exception):
    def __init__(self, status: int, error: str, message: str, request_id: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = ErrorResponse(error=error, message=message, request_id=request_id)


def _json(status: int, body: ErrorResponse) -> JSONResponse:
    headers = {"X-Request-ID": body.request_id} if body.request_id else None
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _json(exc.status, exc.body)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]
        )
        return _json(422, ErrorResponse(error="request_validation_error", message=problems))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        return _json(500, ErrorResponse(error="internal_error", message="unexpected server error"))


# Documented error responses for OpenAPI.
ERROR_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Missing or invalid API key"},
    413: {"model": ErrorResponse, "description": "File larger than the upload limit"},
    415: {"model": ErrorResponse, "description": "The file is not a PDF"},
    422: {"model": ErrorResponse, "description": "Unreadable PDF or invalid request"},
    503: {"model": ErrorResponse, "description": "The language model is not reachable"},
}
