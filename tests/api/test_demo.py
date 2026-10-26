"""The keyless demo route: the browser never sees an API key, and the route is local only."""

from fastapi.testclient import TestClient

from tests.api.test_api import KEY, PDF, scripted
from triage.api.app import create_app
from triage.config import Settings
from triage.llm import FakeProvider


def client(**settings) -> TestClient:
    config = Settings(api_keys=[KEY], **settings)
    return TestClient(
        create_app(settings=config, provider=FakeProvider(scripted), model_check=lambda: True)
    )


def demo_upload(c: TestClient, data: bytes = PDF):
    return c.post("/demo/triage", files={"file": ("claim.pdf", data, "application/pdf")})


def test_the_page_contains_no_api_key_and_no_key_field():
    page = client().get("/").text
    assert KEY not in page
    assert "X-API-Key" not in page
    assert 'type="password"' not in page
    assert "/demo/triage" in page


def test_demo_triage_works_without_a_key_from_this_machine():
    response = demo_upload(client(demo_local_only=False))
    assert response.status_code == 200
    assert response.json()["queue"] == "standard_handler"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_demo_refuses_requests_from_other_machines():
    # TestClient reports the client host as "testclient", which is not a loopback address.
    response = demo_upload(client(demo_local_only=True))
    assert response.status_code == 403
    assert response.json()["error"] == "demo_local_only"


def test_demo_can_be_switched_off():
    c = client(demo_enabled=False, demo_local_only=False)
    assert demo_upload(c).status_code == 404
    assert c.get("/demo/samples").status_code == 404
    assert c.get("/").status_code == 404


def test_demo_applies_the_same_file_checks():
    response = demo_upload(client(demo_local_only=False), data=b"not a pdf")
    assert response.status_code == 415


def test_samples_list_and_download():
    c = client(demo_local_only=False)
    samples = c.get("/demo/samples").json()
    assert {"case_id", "label"} <= set(samples[0])
    assert any(s["case_id"] == "case_002" for s in samples)
    pdf = c.get("/demo/samples/case_002.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert c.get("/demo/samples/case_999.pdf").status_code == 404
    assert c.get("/demo/samples/..%2Fsecret.pdf").status_code == 404


def test_demo_requests_show_up_in_metrics():
    c = client(demo_local_only=False)
    demo_upload(c)
    snap = c.get("/v1/metrics", headers={"X-API-Key": KEY}).json()
    assert snap["triage"]["completed"] == 1


def test_v1_still_requires_the_key():
    c = client(demo_local_only=False)
    response = c.post("/v1/triage", files={"file": ("claim.pdf", PDF, "application/pdf")})
    assert response.status_code == 401
