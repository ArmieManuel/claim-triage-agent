import json
from datetime import date

import pytest

from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.llm import FakeProvider
from triage.nodes.extract import extract
from triage.nodes.ingest import ingest
from triage.nodes.validate import parse_amount, parse_date, validate
from triage.pii import redact
from triage.schemas import ClaimantRole, ExtractionOutput

TODAY = date(2026, 10, 24)
DOC = (
    "Claim number CLM-2026-35152\nPolicy no. POL-78952443\nIncident location Hamburg\n"
    "Police reference DE/48213/26\nA pipe burst."
)


def output(**overrides) -> ExtractionOutput:
    values = {
        "claim_number": "CLM-2026-35152",
        "policy_number": "POL-78952443",
        "date_of_loss": "2026-05-09",
        "claimant_role": "policyholder",
        "amount_claimed": 3627.55,
        "loss_description": "A pipe burst.",
        "location": "Hamburg",
        "policy_start_date": "2024-03-06",
        "police_report_number": None,
        "multiple_claims": False,
    }
    values.update(overrides)
    return ExtractionOutput(**values)


# extract


def test_extract_parses_the_model_answer_and_sends_the_schema():
    fake = FakeProvider([output().model_dump_json()])
    attempt = extract(DOC, fake)
    assert attempt.error is None
    assert attempt.output == output()
    assert attempt.prompt_version == "extract-v1"
    call = fake.calls[0]
    assert DOC in call["prompt"]
    assert call["schema"] == ExtractionOutput.model_json_schema()


def test_extract_puts_retry_feedback_in_the_prompt():
    fake = FakeProvider([output().model_dump_json()])
    extract(DOC, fake, feedback=["date_of_loss '9 May' is not a valid date"])
    assert "date_of_loss '9 May' is not a valid date" in fake.calls[0]["prompt"]


@pytest.mark.parametrize("bad", ["not json", '{"claim_number": 5}', "{}"])
def test_extract_reports_answers_that_do_not_fit_the_schema(bad):
    attempt = extract(DOC, FakeProvider([bad]))
    assert attempt.output is None
    assert attempt.error


# parsing helpers


@pytest.mark.parametrize(
    "text",
    [
        "2026-03-03",
        "03/03/2026",
        "03.03.2026",
        "3 March 2026",
        "March 3, 2026",
        "3rd March 2026",
        "the 3rd day of March in the year 2026",
        "Tue 3rd Mar '26",
        "2026/03/03",
    ],
)
def test_parse_date_accepts_common_formats(text):
    assert parse_date(text) == date(2026, 3, 3)


@pytest.mark.parametrize("text", ["", "last week", "32/01/2026", "2026-13-01"])
def test_parse_date_rejects_non_dates(text):
    assert parse_date(text) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (4250.5, 4250.5),
        ("€1,234.50", 1234.5),
        ("EUR 1234.50", 1234.5),
        ("1,234.50 euros", 1234.5),
        ("€83,302", 83302.0),
        ("about four thousand", None),
    ],
)
def test_parse_amount(value, expected):
    assert parse_amount(value) == expected


# validate


def test_validate_accepts_a_good_answer():
    result = validate(output(), DOC, today=TODAY)
    assert result.ok
    assert result.errors == []
    assert result.missing == []
    assert result.fields.date_of_loss == date(2026, 5, 9)
    assert result.fields.claimant_role == ClaimantRole.POLICYHOLDER


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"date_of_loss": "sometime in May"}, "date_of_loss"),
        ({"date_of_loss": "2026-12-01"}, "future"),
        ({"policy_start_date": "2026-06-01"}, "policy_start_date"),
        ({"amount_claimed": -5}, "amount_claimed"),
        ({"amount_claimed": "lots"}, "amount_claimed"),
        ({"claim_number": "CLM-2026-99999"}, "claim_number"),
        ({"policy_number": "POL-00000000"}, "policy_number"),
        ({"location": "Berlin"}, "location"),
        ({"police_report_number": "DE/11111/26"}, "police_report_number"),
    ],
)
def test_validate_reports_fixable_problems(overrides, problem):
    result = validate(output(**overrides), DOC, today=TODAY)
    assert not result.ok
    assert any(problem in error for error in result.errors)


def test_values_are_matched_against_the_document_ignoring_line_breaks():
    doc = DOC.replace("CLM-2026-35152", "CLM-2026-\n35152")
    assert validate(output(), doc, today=TODAY).ok


@pytest.mark.parametrize("empty", [None, "", "N/A", "null", "unknown", "not stated"])
def test_missing_values_are_reported_but_not_retried(empty):
    result = validate(output(policy_number=empty), DOC, today=TODAY)
    assert result.ok
    assert result.missing == ["policy_number"]
    assert result.fields.policy_number is None


def test_validate_passes_on_the_multiple_claims_flag():
    assert validate(output(multiple_claims=True), DOC, today=TODAY).multiple_claims


@pytest.mark.parametrize("case", load_golden_cases(split="dev"), ids=lambda case: case.case_id)
def test_ground_truth_answers_pass_validation_on_redacted_dev_documents(case):
    """The validator must never reject a correct answer."""
    text = redact(ingest((GOLDEN_DIR / "dev" / case.pdf_file).read_bytes()).text).text
    data = json.loads(case.expected.fields.model_dump_json())
    data["multiple_claims"] = case.expected.multiple_claims
    result = validate(ExtractionOutput(**data), text, today=TODAY)
    assert result.errors == []
    assert result.fields == case.expected.fields
