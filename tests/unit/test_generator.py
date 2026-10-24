import io
import re
from collections import Counter
from datetime import date, timedelta

import pdfplumber
import pytest

from generator.content import format_date
from generator.make_case import make_case
from generator.policy import load_policy
from generator.scenarios import build_specs
from triage.schemas import Category, Queue

SPECS = build_specs()
POLICY = load_policy()


def pdf_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def flat(text: str) -> str:
    """Collapse whitespace and drop thousands separators so wrapped text still matches."""
    return re.sub(r"\s+", " ", text).replace(",", "")


@pytest.fixture(scope="module")
def generated():
    return {spec.case_id: make_case(spec) for spec in SPECS}


def test_specs_have_50_cases_with_10_hard():
    assert len(SPECS) == 50
    assert sum(spec.hard for spec in SPECS) == 10


def test_specs_split_30_dev_20_holdout_without_overlap():
    splits = Counter(spec.split for spec in SPECS)
    assert splits == {"dev": 30, "holdout": 20}
    assert len({spec.case_id for spec in SPECS}) == 50


def test_every_category_appears_in_both_splits():
    for split in ("dev", "holdout"):
        categories = {spec.category for spec in SPECS if spec.split == split}
        assert categories == set(Category)


def test_every_queue_appears_in_dev():
    assert {spec.route for spec in SPECS if spec.split == "dev"} == set(Queue)


def test_layouts_vary():
    assert len({spec.layout for spec in SPECS}) >= 3


def test_hard_case_tags_cover_the_plan():
    tags = {tag for spec in SPECS for tag in spec.tags}
    assert {
        "missing_field",
        "ambiguous_category",
        "multiple_claims",
        "unusual_date",
        "long_description",
    } <= tags


def test_make_case_is_deterministic():
    spec = SPECS[0]
    first, second = make_case(spec), make_case(spec)
    assert first.case == second.case
    assert first.pdf_bytes == second.pdf_bytes


def test_pdf_contains_the_extractable_ground_truth(generated):
    for item in generated.values():
        text = flat(pdf_text(item.pdf_bytes))
        fields = item.case.expected.fields
        for value in (fields.claim_number, fields.policy_number, fields.location):
            if value is not None:
                assert flat(value) in text, (item.case.case_id, value)
        if fields.amount_claimed is not None:
            assert f"{fields.amount_claimed:.2f}".removesuffix(".00") in text, item.case.case_id


def test_pdf_contains_every_pii_value(generated):
    for item in generated.values():
        text = flat(pdf_text(item.pdf_bytes))
        for pii in item.case.pii:
            assert flat(pii.value) in text, (item.case.case_id, pii.kind)


def test_pdf_is_marked_synthetic(generated):
    for item in generated.values():
        assert "SYNTHETIC TEST DOCUMENT" in pdf_text(item.pdf_bytes)


def test_missing_field_cases_really_omit_the_value(generated):
    cases = [item for item in generated.values() if "missing_field" in item.case.tags]
    assert cases
    for item in cases:
        fields = item.case.expected.fields
        assert None in (fields.policy_number, fields.amount_claimed, fields.date_of_loss)
        assert item.case.expected.route == Queue.HUMAN_REVIEW


def test_multiple_claims_case_mentions_two_claim_numbers(generated):
    cases = [item for item in generated.values() if "multiple_claims" in item.case.tags]
    assert cases
    for item in cases:
        numbers = set(re.findall(r"CLM-\d{4}-\d{5}", pdf_text(item.pdf_bytes)))
        assert len(numbers) == 2
        assert item.case.expected.multiple_claims


def test_long_description_cases_are_long(generated):
    cases = [item for item in generated.values() if "long_description" in item.case.tags]
    assert cases
    longest = max(len(item.case.expected.fields.loss_description.split()) for item in cases)
    assert all(len(item.case.expected.fields.loss_description.split()) > 2000 for item in cases)
    assert longest > 3000


def test_format_date_styles():
    d = date(2026, 3, 3)
    assert format_date(d, "dmy_slash") == "03/03/2026"
    assert format_date(d, "long") == "3 March 2026"
    assert format_date(d, "iso") == "2026-03-03"
    assert format_date(d, "ordinal_words") == "the 3rd day of March in the year 2026"
    assert format_date(d, "short_weekday") == "Tue 3rd Mar '26"


def test_ground_truth_routes_follow_the_routing_policy(generated):
    for item in generated.values():
        expected = item.case.expected
        fields = expected.fields
        if expected.route == Queue.HUMAN_REVIEW:
            continue
        new_policy = (
            fields.policy_start_date is not None
            and fields.date_of_loss - fields.policy_start_date
            <= timedelta(days=POLICY.fraud_new_policy_days)
        )
        theft_no_report = (
            expected.category == Category.MOTOR_THEFT and fields.police_report_number is None
        )
        is_fraud = new_policy or theft_no_report
        assert (expected.route == Queue.FRAUD_REVIEW) == is_fraud, item.case.case_id
        if is_fraud:
            continue
        senior = (
            fields.amount_claimed > POLICY.senior_min_amount
            or expected.category in POLICY.always_senior_categories
        )
        assert (expected.route == Queue.SENIOR_HANDLER) == senior, item.case.case_id
        if senior:
            continue
        auto = (
            fields.amount_claimed <= POLICY.auto_max_amount
            and expected.category not in POLICY.never_auto_categories
        )
        expected_queue = Queue.AUTO_PROCESS if auto else Queue.STANDARD_HANDLER
        assert expected.route == expected_queue, item.case.case_id
