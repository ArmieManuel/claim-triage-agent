"""The FastAPI service, tested with FastAPI's TestClient and a scripted fake model."""

import io
import json

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from triage.api.app import create_app
from triage.config import Settings
from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.llm import FakeProvider

KEY = "test-key-123"
CASE = next(c for c in load_golden_cases(split="dev") if c.case_id == "case_013")
PDF = (GOLDEN_DIR / "dev" / CASE.pdf_file).read_bytes()


def scripted(system, prompt, schema):
    props = schema["properties"]
    if "multiple_claims" in props:
        data = json.loads(CASE.expected.fields.model_dump_json())
        return json.dumps({**data, "multiple_claims": False})
    if "confidence" in props:
        return json.dumps(
            {"category": "other", "alternative_category": None, "confidence": 0.9, "reason": "x"}
        )
    return json.dumps({"summary": "One. Two. Three."})


def client(provider=None, model_up=True, **settings) -> TestClient:
    config = Settings(api_keys=[KEY], **settings)
    app = create_app(
        settings=config,
        provider=provider or FakeProvider(scripted),
        model_check=lambda: model_up,
    )
    return TestClient(app)


def upload(c: TestClient, data: bytes = PDF, key: str | None = KEY, name="claim.pdf", **headers):
    if key is not None:
        headers["X-API-Key"] = key
    return c.post("/v1/triage", files={"file": (name, data, "application/pdf")}, headers=headers)


def blank_pdf() -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, invariant=1)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


# health


def test_health_needs_no_key_and_reports_the_model():
    body = client().get("/health").json()
    assert body["status"] == "ok"
    assert body["model_available"] is True
    assert body["model"] == "gemma4:e2b"


def test_health_is_degraded_when_the_model_is_down():
    response = client(model_up=False).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


# authentication


def test_missing_api_key_is_rejected():
    response = upload(client(), key=None)
    assert response.status_code == 401
    assert response.json()["error"] == "missing_api_key"


def test_wrong_api_key_is_rejected():
    response = upload(client(), key="wrong")
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_api_key"


def test_no_configured_keys_means_no_access():
    app = create_app(
        settings=Settings(api_keys=[]), provider=FakeProvider(scripted), model_check=lambda: True
    )
    response = upload(TestClient(app))
    assert response.status_code == 401


# triage


def test_triage_returns_the_result_and_request_id():
    response = upload(client())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["queue"] == "standard_handler"
    assert body["fields"]["claim_number"] == "CLM-2026-35152"
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_client_request_id_is_kept():
    response = upload(client(), **{"X-Request-ID": "abc-123"})
    assert response.json()["request_id"] == "abc-123"
    assert response.headers["X-Request-ID"] == "abc-123"


@pytest.mark.parametrize("data", [b"hello, not a pdf", b"PK\x03\x04 zip file"])
def test_files_that_are_not_pdfs_are_rejected(data):
    response = upload(client(), data=data, name="claim.txt")
    assert response.status_code == 415
    assert response.json()["error"] == "unsupported_media_type"


def test_files_over_the_size_limit_are_rejected():
    response = upload(client(max_upload_mb=0.001))  # about 1 KB
    assert response.status_code == 413
    assert response.json()["error"] == "file_too_large"


def test_unreadable_pdfs_get_a_clear_reason():
    response = upload(client(), data=blank_pdf())
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "unreadable_document"
    assert "no_text" in body["message"]
    assert body["request_id"]


def test_missing_file_field_gets_a_validation_error():
    response = client().post("/v1/triage", headers={"X-API-Key": KEY})
    assert response.status_code == 422
    assert response.json()["error"] == "request_validation_error"


def test_model_offline_gives_503():
    def offline(system, prompt, schema):
        raise ConnectionError("Failed to connect to Ollama")

    response = upload(client(provider=FakeProvider(offline)))
    assert response.status_code == 503
    assert response.json()["error"] == "model_unavailable"


# metrics


def test_metrics_need_a_key():
    assert client().get("/v1/metrics").status_code == 401


def test_metrics_count_requests_queues_and_failures():
    c = client()
    upload(c)
    upload(c, key="wrong")
    upload(c, data=b"not a pdf")
    snap = c.get("/v1/metrics", headers={"X-API-Key": KEY}).json()
    triage = snap["triage"]
    assert triage["completed"] == 1
    assert triage["by_queue"] == {"standard_handler": 1}
    assert triage["errors_by_code"] == {"unsupported_media_type": 1}
    assert snap["http_by_status"]["401"] == 1
    assert triage["latency_p50_s"] is not None


# docs and versioning


def test_openapi_documents_the_v1_route_schemas_and_api_key():
    spec = client().get("/openapi.json").json()
    assert "/v1/triage" in spec["paths"]
    assert {"TriageResult", "ErrorResponse"} <= set(spec["components"]["schemas"])
    assert "APIKeyHeader" in spec["components"]["securitySchemes"]
    documented = spec["paths"]["/v1/triage"]["post"]["responses"]
    assert {"200", "401", "413", "415", "422", "503"} <= set(documented)


def test_docs_page_and_demo_page_are_served():
    c = client()
    assert c.get("/docs").status_code == 200
    demo = c.get("/")
    assert demo.status_code == 200
    assert "<form" in demo.text
    assert "/v1/triage" in demo.text
