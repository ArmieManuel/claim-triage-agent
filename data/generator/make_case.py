"""Builds one golden case (ground truth plus PDF) from a CaseSpec, deterministically."""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from faker import Faker

from generator.content import (
    AMBIGUOUS_STORIES,
    CARS,
    CITIES,
    FAKER_LOCALES,
    INSURERS,
    NATIONAL_IDS,
    NORMAL_DATE_STYLES,
    ROLE_WORDS,
    SECOND_CLAIM_STORY,
    describe,
    format_amount,
    format_date,
    lengthen,
)
from generator.policy import RoutingPolicy, load_policy
from generator.render import Facts, render_pdf
from generator.scenarios import CaseSpec
from triage.schemas import (
    Category,
    ClaimantRole,
    ClaimFields,
    ExpectedOutput,
    GoldenCase,
    PiiItem,
    Queue,
)

FIRST_LOSS_DATE = date(2025, 6, 1)
LOSS_DATE_RANGE_DAYS = 486  # up to 2026-09-30
MOTOR = (Category.MOTOR_COLLISION, Category.MOTOR_THEFT)


@dataclass
class GeneratedCase:
    case: GoldenCase
    pdf_bytes: bytes


def pick_amount(spec: CaseSpec, rng: random.Random, policy: RoutingPolicy) -> float:
    if spec.route == Queue.AUTO_PROCESS:
        low, high = 150, policy.auto_max_amount
    elif spec.route == Queue.STANDARD_HANDLER:
        low, high = policy.auto_max_amount + 100, policy.senior_min_amount - 1000
    elif spec.route == Queue.SENIOR_HANDLER and spec.category == Category.LIABILITY:
        low, high = 3000, 60000
    elif spec.route == Queue.SENIOR_HANDLER:
        low, high = policy.senior_min_amount + 1000, 120000
    elif spec.route == Queue.FRAUD_REVIEW:
        low, high = 3000, 40000
    else:
        low, high = 800, 15000
    amount = rng.uniform(low, high)
    return float(round(amount)) if rng.random() < 0.3 else round(amount, 2)


def pick_role(spec: CaseSpec, rng: random.Random) -> ClaimantRole:
    if spec.category == Category.LIABILITY:
        return ClaimantRole.THIRD_PARTY
    if spec.layout == "letter" and rng.random() < 0.35:
        return ClaimantRole.REPRESENTATIVE
    return ClaimantRole.POLICYHOLDER


def policy_number(rng: random.Random) -> str:
    style = rng.randrange(3)
    if style == 0:
        return f"POL-{rng.randint(10_000_000, 99_999_999)}"
    if style == 1:
        letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(2))
        return f"AL/{rng.randint(100_000, 999_999)}/{letters}"
    return f"DG-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"


def german_tax_id(rng: random.Random) -> str:
    """11 digits, no leading zero. Format only: the real check digit is not computed."""
    return str(rng.randint(1, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(10))


def make_case(spec: CaseSpec, policy: RoutingPolicy | None = None) -> GeneratedCase:
    policy = policy or load_policy()
    rng = random.Random(spec.seed)
    fake = Faker(FAKER_LOCALES[spec.country])
    fake.seed_instance(spec.seed)

    loss = FIRST_LOSS_DATE + timedelta(days=rng.randint(0, LOSS_DATE_RANGE_DAYS))
    if spec.fraud_reason == "new_policy":
        start = loss - timedelta(days=rng.randint(3, policy.fraud_new_policy_days - 2))
    else:
        start = loss - timedelta(days=rng.randint(200, 2000))

    police = None
    police_ref = f"{spec.country}/{rng.randint(10000, 99999)}/{loss:%y}"
    if (spec.category == Category.MOTOR_THEFT and spec.fraud_reason != "no_police_report") or (
        spec.category == Category.MOTOR_COLLISION and rng.random() < 0.4
    ):
        police = police_ref

    amount = pick_amount(spec, rng, policy)
    role = pick_role(spec, rng)
    claim_number = f"CLM-{loss.year}-{rng.randint(10000, 99999)}"
    pol_number = policy_number(rng)
    location = rng.choice(CITIES[spec.country])
    car = rng.choice(CARS)

    writer = fake.name()
    other_name = fake.name() if role != ClaimantRole.POLICYHOLDER else None
    address_lines = fake.address().split("\n")
    address = ", ".join(address_lines)
    phone = fake.phone_number()
    email = fake.email(safe=True)
    national_id = german_tax_id(rng) if spec.country == "DE" else fake.ssn()
    id_labels, id_name = NATIONAL_IDS[spec.country]
    registration = fake.license_plate() if spec.category in MOTOR else None

    if spec.variant in AMBIGUOUS_STORIES:
        description = AMBIGUOUS_STORIES[spec.variant].format(car=car)
    else:
        description = describe(spec.category, rng, car)
    if spec.long_words:
        description = lengthen(description, rng, spec.long_words, spec.category)

    amount_text = format_amount(amount, rng, policy.currency)
    if "amount_in_narrative" in spec.tags:
        description += f" Taking everything together, my total claim is {amount_text}."
        amount_text = None
    if spec.variant == "missing_amount":
        description += " I do not have a final figure for the repairs yet and will send quotes when I have them."
        amount, amount_text = None, None
    if spec.variant == "missing_date":
        description = (
            "I am not sure exactly when this happened as we were away, but I noticed it when we "
            "got back. " + description
        )
    extra = []
    if spec.variant == "two_claims":
        other_claim = f"CLM-{loss.year}-{rng.randint(10000, 99999)}"
        extra.append(SECOND_CLAIM_STORY.format(car=car, other_claim=other_claim))

    date_style = spec.date_style or rng.choice(NORMAL_DATE_STYLES)
    shown_date = None if spec.variant == "missing_date" else format_date(loss, date_style)
    if spec.variant == "missing_policy_number":
        pol_number = None
    sent = loss + timedelta(days=rng.randint(1, 10))

    facts = Facts(
        insurer=rng.choice(INSURERS),
        claim_number=claim_number,
        policy_number=pol_number,
        date_of_loss=shown_date,
        role=role.value,
        role_text=rng.choice(ROLE_WORDS[role.value]),
        amount=amount_text,
        location=location,
        policy_start=format_date(start, rng.choice(NORMAL_DATE_STYLES)),
        police_report=police,
        writer_name=writer,
        other_name=other_name,
        address=address,
        address_lines=address_lines,
        phone=phone,
        email=email,
        national_id=national_id,
        national_id_labels=id_labels,
        national_id_name=id_name,
        vehicle_registration=registration,
        description=description,
        sent_date=format_date(sent, rng.choice(NORMAL_DATE_STYLES)),
        extra_paragraphs=extra,
    )
    pdf_bytes = render_pdf(spec.layout, facts, rng, title=f"Synthetic claim {spec.case_id}")

    fields = ClaimFields(
        claim_number=claim_number,
        policy_number=pol_number,
        date_of_loss=None if spec.variant == "missing_date" else loss,
        claimant_role=role,
        amount_claimed=amount,
        loss_description=description,
        location=location,
        policy_start_date=start,
        police_report_number=police,
    )
    pii = [PiiItem(kind="name", value=writer)]
    if other_name:
        pii.append(PiiItem(kind="name", value=other_name))
    pii += [
        PiiItem(kind="address", value=address),
        PiiItem(kind="phone", value=phone),
        PiiItem(kind="email", value=email),
        PiiItem(kind="national_id", value=national_id),
    ]
    if registration:
        pii.append(PiiItem(kind="vehicle_registration", value=registration))

    case = GoldenCase(
        case_id=spec.case_id,
        split=spec.split,
        hard=spec.hard,
        tags=list(spec.tags),
        layout=spec.layout,
        country=spec.country,
        pdf_file=f"{spec.case_id}.pdf",
        expected=ExpectedOutput(
            fields=fields,
            category=spec.category,
            acceptable_categories=list(spec.acceptable_categories),
            route=spec.route,
            multiple_claims=spec.variant == "two_claims",
        ),
        pii=pii,
    )
    return GeneratedCase(case=case, pdf_bytes=pdf_bytes)
