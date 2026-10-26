"""Pydantic models shared by the agent, the generator and the evaluation harness."""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Category(StrEnum):
    MOTOR_COLLISION = "motor_collision"
    MOTOR_THEFT = "motor_theft"
    PROPERTY_WATER = "property_water"
    PROPERTY_FIRE = "property_fire"
    LIABILITY = "liability"
    OTHER = "other"


class Queue(StrEnum):
    AUTO_PROCESS = "auto_process"
    STANDARD_HANDLER = "standard_handler"
    SENIOR_HANDLER = "senior_handler"
    FRAUD_REVIEW = "fraud_review"
    HUMAN_REVIEW = "human_review"


class ClaimantRole(StrEnum):
    POLICYHOLDER = "policyholder"
    THIRD_PARTY = "third_party"
    REPRESENTATIVE = "representative"


class ClaimFields(BaseModel):
    """Fields extracted from one claim. A value is None when the document does not state it."""

    model_config = ConfigDict(extra="forbid")

    claim_number: str | None = None
    policy_number: str | None = None
    date_of_loss: date | None = None
    claimant_role: ClaimantRole | None = None
    amount_claimed: float | None = Field(default=None, gt=0)
    loss_description: str | None = None
    location: str | None = None
    policy_start_date: date | None = None
    police_report_number: str | None = None


REQUIRED_FIELDS = (
    "claim_number",
    "policy_number",
    "date_of_loss",
    "claimant_role",
    "amount_claimed",
    "loss_description",
    "location",
)


class ExtractionOutput(BaseModel):
    """What the model must answer. Loose types on purpose: the validate node checks them in code."""

    model_config = ConfigDict(extra="forbid")

    claim_number: str | None
    policy_number: str | None
    date_of_loss: str | None = Field(description="YYYY-MM-DD")
    claimant_role: ClaimantRole | None
    amount_claimed: float | str | None = Field(description="Number in euros, e.g. 4250.5")
    loss_description: str | None
    location: str | None
    policy_start_date: str | None = Field(description="YYYY-MM-DD")
    police_report_number: str | None
    multiple_claims: bool


def missing_required_fields(fields: ClaimFields) -> list[str]:
    return [name for name in REQUIRED_FIELDS if getattr(fields, name) is None]


class ExpectedOutput(BaseModel):
    """Ground truth for one golden case."""

    model_config = ConfigDict(extra="forbid")

    fields: ClaimFields
    category: Category
    acceptable_categories: list[Category] = Field(default_factory=list)
    route: Queue
    multiple_claims: bool = False

    @model_validator(mode="after")
    def check_consistency(self) -> "ExpectedOutput":
        if not self.acceptable_categories:
            self.acceptable_categories = [self.category]
        if self.category not in self.acceptable_categories:
            raise ValueError("category must be one of acceptable_categories")
        needs_human = (
            bool(missing_required_fields(self.fields))
            or self.multiple_claims
            or len(self.acceptable_categories) > 1
        )
        if needs_human and self.route != Queue.HUMAN_REVIEW:
            raise ValueError(
                "missing fields, multiple claims or an ambiguous category must route to human_review"
            )
        return self


class NodeTrace(BaseModel):
    """One step of one request: what ran, how long it took, what it cost."""

    node: str
    latency_s: float
    prompt_tokens: int = 0
    output_tokens: int = 0
    outcome: str


class TriageResult(BaseModel):
    """What the agent returns for one claim PDF."""

    request_id: str
    status: Literal["completed", "rejected"]
    queue: Queue | None = None
    reasons: list[str] = Field(default_factory=list)
    category: Category | None = None
    confidence: float | None = None
    fields: ClaimFields | None = None
    multiple_claims: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    extraction_attempts: int = 0
    rejection_reason: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    trace: list[NodeTrace] = Field(default_factory=list)


class PiiItem(BaseModel):
    """One piece of personal data planted in a synthetic document, used to test redaction."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["name", "address", "phone", "email", "national_id", "vehicle_registration"]
    value: str


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    split: Literal["dev", "holdout"]
    hard: bool
    tags: list[str]
    layout: Literal["form", "letter", "email"]
    country: Literal["DE", "IT", "AT"]
    pdf_file: str
    expected: ExpectedOutput
    pii: list[PiiItem]
