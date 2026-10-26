"""FastAPI application.

Run locally:  .venv\\Scripts\\python -m uvicorn triage.api.app:app
Then open http://127.0.0.1:8000/ (demo page, no key needed from this machine) or
http://127.0.0.1:8000/docs (API docs; /v1 routes need the X-API-Key header).
"""

import time
from collections.abc import Callable
from typing import Literal

import httpx
from fastapi import FastAPI, Request
from pydantic import BaseModel

from triage import __version__
from triage.api.demo import make_demo_router
from triage.api.errors import install_error_handlers
from triage.api.service import TriageService
from triage.api.v1 import make_router
from triage.config import Settings
from triage.llm import LLMProvider, make_provider
from triage.observability import Metrics, configure_logging, log
from triage.rules import RoutingPolicy, load_routing_policy


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    model: str
    model_available: bool


def ollama_reachable(settings: Settings) -> bool:
    try:
        return httpx.get(f"{settings.ollama_host}/api/version", timeout=2).is_success
    except Exception:
        return False


def create_app(
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
    model_check: Callable[[], bool] | None = None,
    policy: RoutingPolicy | None = None,
) -> FastAPI:
    settings = settings or Settings()
    provider = provider or make_provider(settings)
    policy = policy or load_routing_policy(settings.routing_config)
    model_check = model_check or (lambda: ollama_reachable(settings))

    app = FastAPI(
        title="Claim Triage Agent",
        version=__version__,
        description=(
            "Extracts, classifies, routes and summarizes synthetic insurance claim PDFs with a "
            "local model. Portfolio project: synthetic data only, never real claims."
        ),
    )
    install_error_handlers(app)
    configure_logging()
    metrics = Metrics()
    app.state.metrics = metrics
    service = TriageService(settings, provider, policy, metrics)
    app.include_router(make_router(service))
    app.include_router(make_demo_router(service))

    @app.middleware("http")
    async def observe(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        latency = time.perf_counter() - started
        metrics.record_http(request.url.path, response.status_code, latency)
        log.info(
            "http_request",
            extra={
                "request_id": response.headers.get("X-Request-ID"),
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_s": round(latency, 4),
            },
        )
        return response

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        up = model_check()
        return HealthResponse(
            status="ok" if up else "degraded",
            version=__version__,
            model=settings.ollama_model,
            model_available=up,
        )

    return app


app = create_app()
