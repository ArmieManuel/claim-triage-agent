"""Scoring one case and summarizing a run. Pure functions, no model calls."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from triage.schemas import GoldenCase, Queue, TriageResult

# Fields scored for exact match. loss_description is free text and is not scored here.
SCORED_FIELDS = (
    "claim_number",
    "policy_number",
    "date_of_loss",
    "claimant_role",
    "amount_claimed",
    "location",
    "policy_start_date",
    "police_report_number",
)


def _plain(value: Any) -> Any:
    """A value as it should appear in cases.csv: dates as ISO text, enums as their value."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return getattr(value, "value", value)


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        return "".join(value.split()).lower()
    return value


def field_correct(name: str, predicted: Any, expected: Any) -> bool:
    """None matches None: saying a value is absent when it is absent is correct."""
    if predicted is None or expected is None:
        return predicted is None and expected is None
    if name == "amount_claimed":
        return abs(float(predicted) - float(expected)) < 0.01
    return _norm(predicted) == _norm(expected)


def score_case(
    case: GoldenCase,
    result: TriageResult | None,
    latency_s: float,
    pii_recall: float,
    error: str = "",
) -> dict[str, Any]:
    expected = case.expected
    row: dict[str, Any] = {
        "case_id": case.case_id,
        "split": case.split,
        "hard": case.hard,
        "tags": ",".join(case.tags),
        "country": case.country,
        "layout": case.layout,
        "status": "error" if result is None else result.status,
        "error": error,
        "expected_queue": expected.route.value,
        "queue": result.queue.value if result and result.queue else "",
        "expected_category": expected.category.value,
        "category": result.category.value if result and result.category else "",
        "confidence": result.confidence if result else None,
        "attempts": result.extraction_attempts if result else 0,
        "latency_s": round(latency_s, 3),
        "prompt_tokens": sum(s.prompt_tokens for s in result.trace) if result else 0,
        "output_tokens": sum(s.output_tokens for s in result.trace) if result else 0,
        "pii_recall": pii_recall,
        "summary_warnings": sum(w.startswith("summary") for w in result.warnings) if result else 0,
        "reasons": " | ".join(result.reasons) if result else "",
    }
    row["queue_correct"] = row["queue"] == row["expected_queue"]
    row["category_correct"] = bool(result and result.category in expected.acceptable_categories)
    # For F1 an acceptable answer on an ambiguous case counts as the primary category.
    row["category_scored"] = (
        row["expected_category"] if row["category_correct"] else (row["category"] or "none")
    )
    fields = result.fields if result else None
    for name in SCORED_FIELDS:
        predicted = getattr(fields, name) if fields else None
        row[f"field_{name}"] = fields is not None and field_correct(
            name, predicted, getattr(expected.fields, name)
        )
        row[f"pred_{name}"] = _plain(predicted)
        row[f"exp_{name}"] = _plain(getattr(expected.fields, name))
    return row


def macro_f1(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    labels = sorted(set(y_true) | set(y_pred))
    scores = []
    for label in labels:
        tp = sum(t == label and p == label for t, p in zip(y_true, y_pred, strict=True))
        fp = sum(t != label and p == label for t, p in zip(y_true, y_pred, strict=True))
        fn = sum(t == label and p != label for t, p in zip(y_true, y_pred, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _rate(series: pd.Series) -> float | None:
    return round(float(series.mean()), 4) if len(series) else None


def summarize_metrics(df: pd.DataFrame) -> dict[str, Any]:
    field_columns = [c for c in df.columns if c.startswith("field_")]
    m: dict[str, Any] = {
        "n_cases": len(df),
        "n_errors": int((df["status"] == "error").sum()),
        "routing_accuracy": _rate(df["queue_correct"]),
        "routing_accuracy_normal": _rate(df.loc[~df["hard"].astype(bool), "queue_correct"]),
        "routing_accuracy_hard": _rate(df.loc[df["hard"].astype(bool), "queue_correct"]),
        "classification_accuracy": _rate(df["category_correct"]),
        "classification_macro_f1": round(
            macro_f1(list(df["expected_category"]), list(df["category_scored"])), 4
        ),
    }
    for column in field_columns:
        m[f"field_accuracy_{column.removeprefix('field_')}"] = _rate(df[column])
    m["field_accuracy_mean"] = round(
        sum(m[f"field_accuracy_{c.removeprefix('field_')}"] for c in field_columns)
        / len(field_columns),
        4,
    )
    m.update(
        {
            "human_review_rate": _rate(df["queue"] == Queue.HUMAN_REVIEW.value),
            "expected_human_review_rate": _rate(df["expected_queue"] == Queue.HUMAN_REVIEW.value),
            "retry_rate": _rate(df["attempts"] > 1),
            "latency_p50_s": round(float(df["latency_s"].quantile(0.5)), 2),
            "latency_p95_s": round(float(df["latency_s"].quantile(0.95)), 2),
            "latency_mean_s": round(float(df["latency_s"].mean()), 2),
            "tokens_prompt_mean": round(float(df["prompt_tokens"].mean()), 1),
            "tokens_output_mean": round(float(df["output_tokens"].mean()), 1),
            "tokens_total": int(df["prompt_tokens"].sum() + df["output_tokens"].sum()),
            "pii_recall": _rate(df["pii_recall"]),
            "summary_warning_rate": _rate(df["summary_warnings"] > 0),
        }
    )
    return m


def check_thresholds(metrics: dict[str, Any], gates: dict[str, dict[str, float]]) -> list[str]:
    failures = []
    for name, minimum in (gates.get("min") or {}).items():
        value = metrics.get(name)
        if value is None or value < minimum:
            failures.append(f"{name} = {value}, gate requires at least {minimum}")
    for name, maximum in (gates.get("max") or {}).items():
        value = metrics.get(name)
        if value is None or value > maximum:
            failures.append(f"{name} = {value}, gate allows at most {maximum}")
    return failures
