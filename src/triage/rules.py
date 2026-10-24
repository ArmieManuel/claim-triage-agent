"""Routing rules in plain Python (step 6). Thresholds come from config/routing.yaml.

Rule order, first match wins (docs/routing_policy.md):
1. human_review: extraction still failing, required field missing, several claims, low confidence
2. fraud_review: loss soon after policy start, or motor theft without a police report
3. senior_handler: large amount, or a category that always needs a senior handler
4. auto_process: small amount in a category that may be automated
5. standard_handler: everything else
"""

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import yaml

from triage.config import Settings
from triage.schemas import Category, ClaimFields, Queue


@dataclass(frozen=True)
class RoutingPolicy:
    currency: str
    auto_max_amount: float
    senior_min_amount: float
    fraud_new_policy_days: int
    always_senior_categories: frozenset[Category]
    never_auto_categories: frozenset[Category]
    min_confidence: float


def load_routing_policy(path: Path | None = None) -> RoutingPolicy:
    path = path or Settings().routing_config
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return RoutingPolicy(
        currency=raw["currency"],
        auto_max_amount=float(raw["auto_max_amount"]),
        senior_min_amount=float(raw["senior_min_amount"]),
        fraud_new_policy_days=int(raw["fraud_new_policy_days"]),
        always_senior_categories=frozenset(Category(c) for c in raw["always_senior_categories"]),
        never_auto_categories=frozenset(Category(c) for c in raw["never_auto_categories"]),
        min_confidence=float(raw["min_confidence"]),
    )


@dataclass(frozen=True)
class RoutingDecision:
    queue: Queue
    reasons: list[str] = field(default_factory=list)


def route(
    fields: ClaimFields,
    *,
    category: Category,
    confidence: float,
    multiple_claims: bool,
    missing: list[str],
    policy: RoutingPolicy,
    extraction_failed: bool = False,
) -> RoutingDecision:
    human = []
    if extraction_failed:
        human.append("extraction still failed validation after the retries")
    if missing:
        human.append(f"required fields missing: {', '.join(missing)}")
    if multiple_claims:
        human.append("the document contains more than one claim")
    if confidence < policy.min_confidence:
        human.append(f"classification confidence {confidence:.2f} is below {policy.min_confidence}")
    if human:
        return RoutingDecision(Queue.HUMAN_REVIEW, human)

    fraud = []
    loss, start = fields.date_of_loss, fields.policy_start_date
    if loss and start and timedelta(0) <= loss - start <= timedelta(policy.fraud_new_policy_days):
        fraud.append(f"loss {(loss - start).days} days after the policy started")
    if category == Category.MOTOR_THEFT and not fields.police_report_number:
        fraud.append("motor theft without a police report number")
    if fraud:
        return RoutingDecision(Queue.FRAUD_REVIEW, fraud)

    amount = fields.amount_claimed or 0.0
    if amount > policy.senior_min_amount:
        return RoutingDecision(
            Queue.SENIOR_HANDLER, [f"amount {amount:,.2f} is above {policy.senior_min_amount:,.0f}"]
        )
    if category in policy.always_senior_categories:
        return RoutingDecision(Queue.SENIOR_HANDLER, [f"{category} claims go to a senior handler"])

    if amount <= policy.auto_max_amount and category not in policy.never_auto_categories:
        return RoutingDecision(
            Queue.AUTO_PROCESS, [f"amount {amount:,.2f} is within {policy.auto_max_amount:,.0f}"]
        )
    return RoutingDecision(Queue.STANDARD_HANDLER, ["no special rule applies"])
