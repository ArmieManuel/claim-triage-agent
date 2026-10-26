"""End-to-end run against the real local model. Skipped by default.

Run with: .venv\\Scripts\\python -m pytest -m local_model
This checks that the whole graph works with real model output, not how good it is.
Quality is measured by the evaluation harness (Phase 4).
"""

import httpx
import pytest

from triage.config import Settings
from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.graph import run_triage
from triage.llm import make_provider

pytestmark = [pytest.mark.integration, pytest.mark.local_model]


@pytest.fixture(autouse=True)
def require_ollama():
    try:
        httpx.get(f"{Settings().ollama_host}/api/version", timeout=3).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("Ollama is not running")


def test_real_model_triages_a_golden_claim_end_to_end():
    case = next(c for c in load_golden_cases(split="dev") if c.case_id == "case_013")
    result = run_triage(
        (GOLDEN_DIR / "dev" / case.pdf_file).read_bytes(), make_provider(Settings())
    )
    assert result.status == "completed"
    assert result.queue is not None
    assert result.summary
    assert result.extraction_attempts >= 1
    assert sum(step.prompt_tokens for step in result.trace) > 0
