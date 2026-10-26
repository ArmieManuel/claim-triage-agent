"""Every path through the LangGraph workflow, with a scripted fake model."""

import json
import re
from datetime import date

import pytest

from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.graph import MAX_RETRIES, run_triage
from triage.llm import FakeProvider
from triage.schemas import GoldenCase, Queue

pytestmark = pytest.mark.integration

TODAY = date(2026, 10, 26)
DEV = {case.case_id: case for case in load_golden_cases(split="dev")}
HAPPY = DEV["case_013"]  # German claim form, category other, standard_handler
MISSING = next(
    c for c in DEV.values() if "missing_field" in c.tags and not c.expected.fields.policy_number
)
PIPELINE = ["ingest", "redact_pii", "extract", "validate", "classify", "route", "summarize"]


def pdf(case: GoldenCase) -> bytes:
    return (GOLDEN_DIR / case.split / case.pdf_file).read_bytes()


def truth(case: GoldenCase, **overrides) -> str:
    data = json.loads(case.expected.fields.model_dump_json())
    data["multiple_claims"] = case.expected.multiple_claims
    data.update(overrides)
    return json.dumps(data)


def classification(case: GoldenCase, confidence: float = 0.95) -> str:
    return json.dumps(
        {
            "category": case.expected.category,
            "alternative_category": None,
            "confidence": confidence,
            "reason": "Fits.",
        }
    )


class ScriptedModel:
    """Answers each kind of request from its own script, decided by the JSON schema asked for."""

    def __init__(self, extractions, classify_answer, summary="Claim filed by [NAME_1]. Done."):
        self.extractions = list(extractions)
        self.classify_answer = classify_answer
        self.summary = summary

    def __call__(self, system, prompt, schema):
        props = schema["properties"]
        if "multiple_claims" in props:
            assert self.extractions, "unexpected extra extraction call"
            return self.extractions.pop(0)
        if "confidence" in props:
            return self.classify_answer
        return json.dumps({"summary": self.summary})


def triage(case, extractions, confidence=0.95, **kwargs):
    model = FakeProvider(ScriptedModel(extractions, classification(case, confidence)))
    result = run_triage(pdf(case), model, today=TODAY, **kwargs)
    return result, model


def kinds(model: FakeProvider) -> list[str]:
    names = {"multiple_claims": "extract", "confidence": "classify", "summary": "summarize"}
    return [
        next(v for k, v in names.items() if k in call["schema"]["properties"])
        for call in model.calls
    ]


def test_happy_path_returns_the_full_result():
    result, model = triage(HAPPY, [truth(HAPPY)])
    assert result.status == "completed"
    assert result.queue == HAPPY.expected.route == Queue.STANDARD_HANDLER
    assert result.category == HAPPY.expected.category
    assert result.fields == HAPPY.expected.fields
    assert result.extraction_attempts == 1
    assert [step.node for step in result.trace] == PIPELINE
    assert kinds(model) == ["extract", "classify", "summarize"]
    assert set(result.prompt_versions) == {"extract", "classify", "summarize"}
    assert re.fullmatch(r"[0-9a-f-]{36}", result.request_id)


def test_no_personal_data_reaches_the_model():
    _, model = triage(HAPPY, [truth(HAPPY)])
    sent = " ".join(call["prompt"] for call in model.calls)
    flat = re.sub(r"\s+", " ", sent)
    for pii in HAPPY.pii:
        assert re.sub(r"\s+", " ", pii.value) not in flat, pii.kind


def test_placeholders_in_the_summary_are_restored_for_the_handler():
    result, _ = triage(HAPPY, [truth(HAPPY)])
    name = next(p.value for p in HAPPY.pii if p.kind == "name")
    assert result.summary == f"Claim filed by {name}. Done."


def test_request_id_is_passed_through():
    result, _ = triage(HAPPY, [truth(HAPPY)], request_id="req-123")
    assert result.request_id == "req-123"


def test_retry_then_success():
    bad = truth(HAPPY, date_of_loss="sometime in May")
    result, model = triage(HAPPY, [bad, truth(HAPPY)])
    assert result.queue == HAPPY.expected.route
    assert result.extraction_attempts == 2
    assert "is not a valid date" in model.calls[1]["prompt"]
    assert [s.node for s in result.trace][:6] == [
        "ingest",
        "redact_pii",
        "extract",
        "validate",
        "extract",
        "validate",
    ]


def test_answer_that_is_not_json_is_retried():
    result, _ = triage(HAPPY, ["not json at all", truth(HAPPY)])
    assert result.extraction_attempts == 2
    assert result.queue == HAPPY.expected.route


def test_retry_then_fallback_to_human_review():
    bad = truth(HAPPY, claim_number="CLM-0000-00000")
    result, model = triage(HAPPY, [bad] * (MAX_RETRIES + 1))
    assert result.queue == Queue.HUMAN_REVIEW
    assert result.extraction_attempts == MAX_RETRIES + 1
    assert any("validation" in reason for reason in result.reasons)
    assert kinds(model) == ["extract"] * (MAX_RETRIES + 1)
    assert result.trace[-1].node == "human_review"


def test_low_confidence_goes_to_human_review():
    result, model = triage(HAPPY, [truth(HAPPY)], confidence=0.4)
    assert result.queue == Queue.HUMAN_REVIEW
    assert any("confidence" in reason for reason in result.reasons)
    assert kinds(model) == ["extract", "classify", "summarize"]


def test_multiple_claims_go_to_human_review():
    result, _ = triage(HAPPY, [truth(HAPPY, multiple_claims=True)])
    assert result.queue == Queue.HUMAN_REVIEW
    assert result.multiple_claims


def test_missing_field_goes_to_human_review_without_retrying():
    result, model = triage(MISSING, [truth(MISSING)])
    assert result.queue == Queue.HUMAN_REVIEW
    assert result.extraction_attempts == 1
    assert "policy_number" in result.missing_fields
    assert kinds(model).count("extract") == 1


@pytest.mark.parametrize(("data", "reason"), [(b"not a pdf", "not_a_pdf"), (b"", "empty")])
def test_unreadable_pdf_is_rejected_without_model_calls(data, reason):
    model = FakeProvider([])
    result = run_triage(data, model, today=TODAY)
    assert result.status == "rejected"
    assert result.rejection_reason == reason
    assert result.queue is None
    assert model.calls == []
    assert [s.node for s in result.trace] == ["ingest"]


def test_trace_records_tokens_and_latency_for_model_steps():
    result, _ = triage(HAPPY, [truth(HAPPY)])
    steps = {s.node: s for s in result.trace}
    assert steps["extract"].prompt_tokens > 0
    assert steps["classify"].output_tokens > 0
    assert all(s.latency_s >= 0 for s in result.trace)
    assert steps["route"].outcome == "standard_handler"
