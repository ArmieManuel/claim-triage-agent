"""Step 4: deterministic checks on the model's answer.

Errors are problems a retry can fix (bad date, value not found in the document).
Missing values are not retried: a retry cannot add data the document does not contain,
so they go to routing, which sends the claim to human review.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from triage.schemas import ClaimFields, ExtractionOutput, missing_required_fields

EMPTY = {"", "n/a", "na", "null", "none", "unknown", "not stated", "not provided", "-"}
MONTH_NAMES = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
MONTHS = {name: i for i, name in enumerate(MONTH_NAMES, start=1)}
MONTHS.update({name[:3]: i for name, i in list(MONTHS.items())})
MONTHS["sept"] = 9
ISO = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
DAY_FIRST = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{2}|\d{4})$")
# Fields whose value must be copied from the document, never invented.
GROUNDED = ("claim_number", "policy_number", "location", "police_report_number")
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DATE_PATTERNS = (
    re.compile(r"(?<![\w/.-])\d{4}[-/]\d{1,2}[-/]\d{1,2}(?![\d/-])"),
    re.compile(r"(?<![\w/.-])\d{1,2}[./]\d{1,2}[./](?:\d{4}|\d{2})(?![\d/])"),
    re.compile(
        rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?{_MONTH}(?:\s+in\s+the\s+year)?,?\s+"
        r"(?:'\d{2}|\d{4})\b",
        re.IGNORECASE,
    ),
    re.compile(rf"\b{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b", re.IGNORECASE),
)
DAY_FIRST_HINT = "Numeric dates in these documents are day first: 11/06/2025 is 11 June 2025"


@dataclass
class ValidationResult:
    fields: ClaimFields
    errors: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    multiple_claims: bool = False
    corrections: list[str] = field(default_factory=list)  # fixed in code, no retry needed

    @property
    def ok(self) -> bool:
        return not self.errors


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date(text: str) -> date | None:
    """Parse ISO, day-first numeric (European) and English written dates."""
    text = text.strip()
    if match := ISO.match(text):
        return _safe_date(*(int(g) for g in match.groups()))
    if match := DAY_FIRST.match(text):
        day, month, year = (int(g) for g in match.groups())
        return _safe_date(year + 2000 if year < 100 else year, month, day)
    words = text.lower()
    words = re.sub(r"'(\d{2})\b", r"20\1", words)
    words = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", words)
    words = re.sub(r"[,.]", " ", words)
    tokens = words.split()
    month = next((MONTHS[t] for t in tokens if t in MONTHS), None)
    numbers = [t for t in tokens if t.isdigit()]
    years = [int(t) for t in numbers if len(t) == 4]
    days = [int(t) for t in numbers if len(t) <= 2]
    if month and len(years) == 1 and len(days) == 1:
        return _safe_date(years[0], month, days[0])
    return None


def dates_in(text: str) -> set[date]:
    """Every date written in the document, read day first when numeric."""
    found = set()
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            parsed = parse_date(" ".join(match.group(0).split()))
            if parsed:
                found.add(parsed)
    return found


def parse_amount(value: float | str | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    cleaned = re.sub(r"(?i)euros?|eur|€|\s", "", value).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clean(value):
    if isinstance(value, str):
        value = value.strip()
        return None if value.lower() in EMPTY else value
    return value


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def validate(
    output: ExtractionOutput, document: str, today: date | None = None
) -> ValidationResult:
    today = today or date.today()
    raw = {name: _clean(value) for name, value in output.model_dump().items()}
    errors: list[str] = []

    dates: dict[str, date | None] = {}
    for name in ("date_of_loss", "policy_start_date"):
        dates[name] = parse_date(raw[name]) if raw[name] else None
        if raw[name] and dates[name] is None:
            errors.append(f"{name} '{raw[name]}' is not a valid date, use YYYY-MM-DD")
    loss, start = dates["date_of_loss"], dates["policy_start_date"]
    if loss and loss > today:
        errors.append(f"date_of_loss {loss} is in the future")
        loss = None
    if loss and start and start > loss:
        errors.append(f"policy_start_date {start} is after date_of_loss {loss}")
        start = None
    written = dates_in(document)
    if loss and loss not in written:
        errors.append(f"date_of_loss {loss} does not appear in the document. {DAY_FIRST_HINT}")
        loss = None
    if start and start not in written:
        errors.append(
            f"policy_start_date {start} does not appear in the document. {DAY_FIRST_HINT}"
        )
        start = None

    amount = parse_amount(raw["amount_claimed"]) if raw["amount_claimed"] is not None else None
    if raw["amount_claimed"] is not None and (amount is None or amount <= 0):
        errors.append(
            f"amount_claimed '{raw['amount_claimed']}' must be a positive number in euros"
        )
        amount = None

    squashed = _squash(document)
    for name in GROUNDED:
        if raw[name] and _squash(raw[name]) not in squashed:
            errors.append(f"{name} '{raw[name]}' does not appear in the document")
            raw[name] = None

    corrections: list[str] = []
    police = raw["police_report_number"]
    for other in ("claim_number", "policy_number"):
        if police and raw[other] and _squash(police) == _squash(raw[other]):
            corrections.append(
                f"police_report_number '{police}' equals the {other}, treated as not stated"
            )
            raw["police_report_number"] = police = None

    fields = ClaimFields(
        claim_number=raw["claim_number"],
        policy_number=raw["policy_number"],
        date_of_loss=loss,
        claimant_role=raw["claimant_role"],
        amount_claimed=amount,
        loss_description=raw["loss_description"],
        location=raw["location"],
        policy_start_date=start,
        police_report_number=raw["police_report_number"],
    )
    return ValidationResult(
        fields=fields,
        errors=errors,
        missing=missing_required_fields(fields) if not errors else [],
        multiple_claims=bool(output.multiple_claims),
        corrections=corrections,
    )
