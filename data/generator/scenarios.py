"""The 50 golden case specifications: what each case is designed to test."""

import random
from dataclasses import dataclass, field

from triage.schemas import Category, Queue

C = Category
Q = Queue

# Normal cases: category -> target queues. Fraud entries name the fraud signal.
NORMAL_ROUTES: dict[Category, list[str]] = {
    C.MOTOR_COLLISION: [
        "auto",
        "auto",
        "auto",
        "standard",
        "standard",
        "standard",
        "standard",
        "senior",
        "fraud:new_policy",
    ],
    C.MOTOR_THEFT: [
        "standard",
        "standard",
        "standard",
        "senior",
        "fraud:no_police_report",
        "fraud:new_policy",
    ],
    C.PROPERTY_WATER: [
        "auto",
        "auto",
        "auto",
        "standard",
        "standard",
        "standard",
        "senior",
        "fraud:new_policy",
    ],
    C.PROPERTY_FIRE: ["auto", "standard", "standard", "senior", "senior", "fraud:new_policy"],
    C.LIABILITY: ["senior", "senior", "senior", "senior", "fraud:new_policy"],
    C.OTHER: ["auto", "auto", "auto", "auto", "standard", "standard"],
}
DEV_SHARE = {
    C.MOTOR_COLLISION: 5,
    C.MOTOR_THEFT: 4,
    C.PROPERTY_WATER: 5,
    C.PROPERTY_FIRE: 4,
    C.LIABILITY: 3,
    C.OTHER: 3,
}
QUEUE_BY_NAME = {
    "auto": Q.AUTO_PROCESS,
    "standard": Q.STANDARD_HANDLER,
    "senior": Q.SENIOR_HANDLER,
    "fraud": Q.FRAUD_REVIEW,
}
LAYOUTS = ("form", "letter", "email")
COUNTRIES = ("DE", "IT", "AT")


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    seed: int
    split: str
    category: Category
    route: Queue
    layout: str
    country: str = "DE"
    hard: bool = False
    tags: tuple[str, ...] = ()
    variant: str = "normal"
    fraud_reason: str | None = None
    acceptable_categories: tuple[Category, ...] = field(default=())
    date_style: str | None = None
    long_words: int = 0


# (variant, split, category, route, layout, tags, extra)
HARD_CASES = [
    (
        "missing_policy_number",
        "dev",
        C.PROPERTY_WATER,
        Q.HUMAN_REVIEW,
        "form",
        ("missing_field",),
        {},
    ),
    ("missing_amount", "dev", C.MOTOR_COLLISION, Q.HUMAN_REVIEW, "letter", ("missing_field",), {}),
    (
        "ambiguous_water_fire",
        "dev",
        C.PROPERTY_WATER,
        Q.HUMAN_REVIEW,
        "letter",
        ("ambiguous_category",),
        {"acceptable_categories": (C.PROPERTY_WATER, C.PROPERTY_FIRE)},
    ),
    ("two_claims", "dev", C.PROPERTY_WATER, Q.HUMAN_REVIEW, "email", ("multiple_claims",), {}),
    (
        "unusual_date_words",
        "dev",
        C.MOTOR_COLLISION,
        Q.STANDARD_HANDLER,
        "letter",
        ("unusual_date",),
        {"date_style": "ordinal_words"},
    ),
    (
        "long_fire",
        "dev",
        C.PROPERTY_FIRE,
        Q.STANDARD_HANDLER,
        "form",
        ("long_description",),
        {"long_words": 2400},
    ),
    ("missing_date", "holdout", C.OTHER, Q.HUMAN_REVIEW, "email", ("missing_field",), {}),
    (
        "ambiguous_theft_collision",
        "holdout",
        C.MOTOR_THEFT,
        Q.HUMAN_REVIEW,
        "form",
        ("ambiguous_category",),
        {"acceptable_categories": (C.MOTOR_THEFT, C.MOTOR_COLLISION)},
    ),
    (
        "unusual_date_short",
        "holdout",
        C.PROPERTY_WATER,
        Q.AUTO_PROCESS,
        "email",
        ("unusual_date",),
        {"date_style": "short_weekday"},
    ),
    (
        "long_liability_amount_in_text",
        "holdout",
        C.LIABILITY,
        Q.SENIOR_HANDLER,
        "letter",
        ("long_description", "amount_in_narrative"),
        {"long_words": 3300},
    ),
]


def build_specs() -> list[CaseSpec]:
    rng = random.Random(2026)
    drafts = []  # (split, kwargs)
    for category, routes in NORMAL_ROUTES.items():
        shuffled = routes[:]
        rng.shuffle(shuffled)
        for index, target in enumerate(shuffled):
            name, _, reason = target.partition(":")
            split = "dev" if index < DEV_SHARE[category] else "holdout"
            drafts.append(
                (
                    split,
                    {
                        "category": category,
                        "route": QUEUE_BY_NAME[name],
                        "layout": rng.choice(LAYOUTS),
                        "fraud_reason": reason or None,
                    },
                )
            )
    for variant, split, category, route, layout, tags, extra in HARD_CASES:
        drafts.append(
            (
                split,
                {
                    "category": category,
                    "route": route,
                    "layout": layout,
                    "hard": True,
                    "tags": tags,
                    "variant": variant,
                    **extra,
                },
            )
        )

    rng.shuffle(drafts)
    drafts.sort(key=lambda d: d[0] != "dev")  # stable: dev first, shuffled within each split
    return [
        CaseSpec(
            case_id=f"case_{number:03d}",
            seed=number * 7919,
            split=split,
            country=COUNTRIES[(number - 1) % len(COUNTRIES)],
            **kwargs,
        )
        for number, (split, kwargs) in enumerate(drafts, start=1)
    ]
