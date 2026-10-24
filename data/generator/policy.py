"""Reads the routing thresholds the ground truth is designed against."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from triage.schemas import Category

ROUTING_CONFIG = Path(__file__).resolve().parents[2] / "config" / "routing.yaml"


@dataclass(frozen=True)
class RoutingPolicy:
    auto_max_amount: float
    senior_min_amount: float
    fraud_new_policy_days: int
    always_senior_categories: frozenset[Category]
    never_auto_categories: frozenset[Category]


def load_policy(path: Path = ROUTING_CONFIG) -> RoutingPolicy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return RoutingPolicy(
        auto_max_amount=float(raw["auto_max_amount"]),
        senior_min_amount=float(raw["senior_min_amount"]),
        fraud_new_policy_days=int(raw["fraud_new_policy_days"]),
        always_senior_categories=frozenset(Category(c) for c in raw["always_senior_categories"]),
        never_auto_categories=frozenset(Category(c) for c in raw["never_auto_categories"]),
    )
