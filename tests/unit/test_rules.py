from datetime import date

import pytest

from triage.golden import load_golden_cases
from triage.rules import load_routing_policy, route
from triage.schemas import Category, ClaimantRole, ClaimFields, Queue, missing_required_fields

POLICY = load_routing_policy()
C, Q = Category, Queue


def fields(**overrides) -> ClaimFields:
    values = {
        "claim_number": "CLM-2026-00001",
        "policy_number": "POL-1",
        "date_of_loss": date(2026, 5, 1),
        "claimant_role": ClaimantRole.POLICYHOLDER,
        "amount_claimed": 5000.0,
        "loss_description": "A pipe burst.",
        "location": "Graz",
        "policy_start_date": date(2023, 1, 1),
        "police_report_number": None,
    }
    values.update(overrides)
    return ClaimFields(**values)


def decide(category=C.PROPERTY_WATER, confidence=0.95, multiple=False, failed=False, **overrides):
    claim = fields(**overrides)
    return route(
        claim,
        category=category,
        confidence=confidence,
        multiple_claims=multiple,
        missing=missing_required_fields(claim),
        policy=POLICY,
        extraction_failed=failed,
    )


def test_policy_loads_thresholds_from_config():
    assert POLICY.currency == "EUR"
    assert POLICY.auto_max_amount == 2500
    assert POLICY.senior_min_amount == 25000
    assert POLICY.fraud_new_policy_days == 30
    assert POLICY.min_confidence == 0.7


@pytest.mark.parametrize(
    ("kwargs", "queue"),
    [
        ({}, Q.STANDARD_HANDLER),
        ({"amount_claimed": 2500.0}, Q.AUTO_PROCESS),
        ({"amount_claimed": 2500.01}, Q.STANDARD_HANDLER),
        ({"amount_claimed": 25000.0}, Q.STANDARD_HANDLER),
        ({"amount_claimed": 25000.01}, Q.SENIOR_HANDLER),
        ({"category": C.LIABILITY, "amount_claimed": 900.0}, Q.SENIOR_HANDLER),
        (
            {"category": C.MOTOR_THEFT, "amount_claimed": 900.0, "police_report_number": "DE/1/26"},
            Q.STANDARD_HANDLER,
        ),
        ({"category": C.MOTOR_THEFT, "police_report_number": None}, Q.FRAUD_REVIEW),
        ({"policy_start_date": date(2026, 4, 1)}, Q.FRAUD_REVIEW),
        ({"policy_start_date": date(2026, 3, 31)}, Q.STANDARD_HANDLER),
        ({"policy_number": None}, Q.HUMAN_REVIEW),
        ({"multiple": True}, Q.HUMAN_REVIEW),
        ({"confidence": 0.69}, Q.HUMAN_REVIEW),
        ({"confidence": 0.7}, Q.STANDARD_HANDLER),
        ({"failed": True}, Q.HUMAN_REVIEW),
    ],
)
def test_route_applies_each_rule(kwargs, queue):
    assert decide(**kwargs).queue == queue


def test_rule_order_human_review_beats_fraud_beats_senior():
    assert decide(policy_start_date=date(2026, 4, 20), confidence=0.2).queue == Q.HUMAN_REVIEW
    assert (
        decide(policy_start_date=date(2026, 4, 20), amount_claimed=90000.0).queue == Q.FRAUD_REVIEW
    )


def test_route_explains_its_decision():
    decision = decide(policy_number=None, confidence=0.3)
    assert any("policy_number" in reason for reason in decision.reasons)
    assert any("confidence" in reason for reason in decision.reasons)


@pytest.mark.parametrize("case", load_golden_cases(), ids=lambda case: case.case_id)
def test_rules_reproduce_every_golden_route(case):
    """Given the correct fields and category, the rules must give the designed queue."""
    expected = case.expected
    ambiguous = len(expected.acceptable_categories) > 1
    decision = route(
        expected.fields,
        category=expected.category,
        confidence=0.5 if ambiguous else 1.0,
        multiple_claims=expected.multiple_claims,
        missing=missing_required_fields(expected.fields),
        policy=POLICY,
    )
    assert decision.queue == expected.route
