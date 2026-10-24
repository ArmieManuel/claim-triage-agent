from datetime import date

import pytest
from pydantic import ValidationError

from triage.schemas import (
    Category,
    ClaimantRole,
    ClaimFields,
    ExpectedOutput,
    GoldenCase,
    PiiItem,
    Queue,
    missing_required_fields,
)


def full_fields(**overrides):
    values = {
        "claim_number": "CLM-2026-00417",
        "policy_number": "POL-12345678",
        "date_of_loss": date(2026, 3, 3),
        "claimant_role": ClaimantRole.POLICYHOLDER,
        "amount_claimed": 4250.0,
        "loss_description": "A burst pipe flooded the kitchen.",
        "location": "Leeds",
    }
    values.update(overrides)
    return ClaimFields(**values)


def golden(expected, **overrides):
    values = {
        "case_id": "case_001",
        "split": "dev",
        "hard": False,
        "tags": [],
        "layout": "form",
        "country": "DE",
        "pdf_file": "case_001.pdf",
        "expected": expected,
        "pii": [
            PiiItem(kind="name", value="Natalia Klemt"),
            PiiItem(kind="national_id", value="12345678901"),
        ],
    }
    values.update(overrides)
    return GoldenCase(**values)


def test_claim_fields_reject_non_positive_amount():
    with pytest.raises(ValidationError):
        full_fields(amount_claimed=0)


def test_claim_fields_reject_unknown_keys():
    with pytest.raises(ValidationError):
        ClaimFields(claim_number="X", colour="red")


def test_claim_fields_parse_iso_dates_from_json():
    fields = ClaimFields.model_validate_json('{"date_of_loss": "2026-03-03"}')
    assert fields.date_of_loss == date(2026, 3, 3)


def test_missing_required_fields_lists_absent_values():
    fields = full_fields(policy_number=None, amount_claimed=None)
    assert missing_required_fields(fields) == ["policy_number", "amount_claimed"]


def test_missing_required_fields_ignores_optional_fields():
    assert missing_required_fields(full_fields()) == []


def test_expected_category_must_be_acceptable():
    with pytest.raises(ValidationError):
        ExpectedOutput(
            fields=full_fields(),
            category=Category.PROPERTY_FIRE,
            acceptable_categories=[Category.PROPERTY_WATER],
            route=Queue.STANDARD_HANDLER,
            multiple_claims=False,
        )


def test_acceptable_categories_default_to_the_category():
    expected = ExpectedOutput(
        fields=full_fields(),
        category=Category.PROPERTY_WATER,
        route=Queue.STANDARD_HANDLER,
    )
    assert expected.acceptable_categories == [Category.PROPERTY_WATER]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fields": full_fields(policy_number=None)},
        {"multiple_claims": True},
        {"acceptable_categories": [Category.PROPERTY_WATER, Category.PROPERTY_FIRE]},
    ],
)
def test_cases_needing_a_human_must_route_to_human_review(kwargs):
    values = {
        "fields": full_fields(),
        "category": Category.PROPERTY_WATER,
        "route": Queue.STANDARD_HANDLER,
    }
    values.update(kwargs)
    with pytest.raises(ValidationError):
        ExpectedOutput(**values)


def test_golden_case_rejects_countries_outside_scope():
    with pytest.raises(ValidationError):
        golden(
            ExpectedOutput(
                fields=full_fields(), category=Category.OTHER, route=Queue.STANDARD_HANDLER
            ),
            country="GB",
        )


def test_golden_case_round_trips_through_json():
    case = golden(
        ExpectedOutput(
            fields=full_fields(), category=Category.PROPERTY_WATER, route=Queue.STANDARD_HANDLER
        )
    )
    assert GoldenCase.model_validate_json(case.model_dump_json()) == case
