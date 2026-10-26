import json
from datetime import date

import pandas as pd
import pytest

from evals.metrics import (
    check_thresholds,
    field_correct,
    macro_f1,
    summarize_metrics,
)
from evals.regression import compare
from evals.run_eval import evaluate, main
from triage.golden import load_golden_cases
from triage.llm import FakeProvider
from triage.schemas import ClaimantRole

# field_correct


@pytest.mark.parametrize(
    ("name", "predicted", "expected", "ok"),
    [
        ("claim_number", "CLM-2026-1", "CLM-2026-1", True),
        ("location", " hamburg ", "Hamburg", True),
        ("policy_number", "AL/1 /X", "AL/1/X", True),
        ("policy_number", None, None, True),
        ("policy_number", None, "POL-1", False),
        ("policy_number", "POL-1", None, False),
        ("amount_claimed", 3627.554, 3627.55, True),
        ("amount_claimed", 3627.0, 3627.55, False),
        ("date_of_loss", date(2026, 5, 9), date(2026, 5, 9), True),
        ("claimant_role", ClaimantRole.THIRD_PARTY, ClaimantRole.POLICYHOLDER, False),
    ],
)
def test_field_correct(name, predicted, expected, ok):
    assert field_correct(name, predicted, expected) is ok


def test_macro_f1_matches_a_hand_computed_example():
    y_true = ["a", "a", "b", "b"]
    y_pred = ["a", "b", "b", "b"]
    # a: precision 1, recall 0.5 -> F1 0.667; b: precision 0.667, recall 1 -> F1 0.8
    assert macro_f1(y_true, y_pred) == pytest.approx((2 / 3 + 0.8) / 2)


def rows(**overrides):
    base = {
        "status": "completed",
        "error": "",
        "hard": False,
        "queue_correct": True,
        "category_correct": True,
        "expected_category": "other",
        "category_scored": "other",
        "queue": "standard_handler",
        "expected_queue": "standard_handler",
        "attempts": 1,
        "latency_s": 10.0,
        "prompt_tokens": 1000,
        "output_tokens": 200,
        "pii_recall": 1.0,
        "summary_warnings": 0,
        **{f"field_{name}": True for name in ("claim_number", "location")},
    }
    data = [dict(base) for _ in range(4)]
    for i, change in overrides.items():
        data[int(i[1:])].update(change)
    return pd.DataFrame(data)


def test_summarize_metrics_computes_the_planned_metrics():
    df = rows(
        r0={"queue_correct": False, "queue": "human_review", "attempts": 2, "latency_s": 40.0},
        r1={"field_location": False, "hard": True},
    )
    m = summarize_metrics(df)
    assert m["n_cases"] == 4
    assert m["routing_accuracy"] == 0.75
    assert m["routing_accuracy_hard"] == 1.0
    assert m["field_accuracy_location"] == 0.75
    assert m["field_accuracy_mean"] == pytest.approx((1.0 + 0.75) / 2)
    assert m["human_review_rate"] == 0.25
    assert m["retry_rate"] == 0.25
    assert m["latency_p50_s"] == 10.0
    assert m["latency_p95_s"] == pytest.approx(35.5)
    assert m["tokens_prompt_mean"] == 1000
    assert m["classification_accuracy"] == 1.0


def test_errors_count_as_wrong_answers():
    df = rows(r3={"status": "error", "error": "boom", "queue_correct": False})
    m = summarize_metrics(df)
    assert m["n_errors"] == 1
    assert m["routing_accuracy"] == 0.75


def test_check_thresholds_reports_each_failed_gate():
    metrics = {"routing_accuracy": 0.6, "latency_p95_s": 90.0, "pii_recall": 1.0}
    gates = {"min": {"routing_accuracy": 0.7, "pii_recall": 0.95}, "max": {"latency_p95_s": 60}}
    failures = check_thresholds(metrics, gates)
    assert len(failures) == 2
    assert any("routing_accuracy" in f for f in failures)
    assert any("latency_p95_s" in f for f in failures)
    assert check_thresholds(metrics, {}) == []


# regression


def test_compare_flags_worse_metrics_only():
    before = {"routing_accuracy": 0.8, "field_accuracy_mean": 0.9, "latency_p95_s": 50.0}
    after = {"routing_accuracy": 0.7, "field_accuracy_mean": 0.91, "latency_p95_s": 70.0}
    flagged = {r.metric for r in compare(before, after)}
    assert flagged == {"routing_accuracy", "latency_p95_s"}


def test_compare_ignores_noise_within_tolerance():
    before = {"routing_accuracy": 0.80, "latency_p95_s": 50.0}
    after = {"routing_accuracy": 0.79, "latency_p95_s": 55.0}
    assert compare(before, after) == []


# end to end with a fake model


CASES = [c for c in load_golden_cases(split="dev") if c.case_id in {"case_013", "case_018"}]


def perfect_model(system, prompt, schema):
    case = next(c for c in CASES if c.expected.fields.claim_number in prompt)
    props = schema["properties"]
    if "multiple_claims" in props:
        data = json.loads(case.expected.fields.model_dump_json())
        return json.dumps({**data, "multiple_claims": case.expected.multiple_claims})
    if "confidence" in props:
        return json.dumps(
            {
                "category": case.expected.category,
                "alternative_category": None,
                "confidence": 0.9,
                "reason": "x",
            }
        )
    return json.dumps({"summary": "One. Two. Three."})


def test_evaluate_scores_each_case():
    df = evaluate(CASES, FakeProvider(perfect_model), today=date(2026, 10, 26))
    assert list(df["case_id"]) == ["case_013", "case_018"]
    assert df["queue_correct"].all()
    assert df["field_claim_number"].all()
    assert (df["pii_recall"] == 1.0).all()
    first = df.iloc[0]
    assert first["pred_claim_number"] == first["exp_claim_number"] == "CLM-2026-35152"
    assert first["pred_police_report_number"] is None


def test_main_writes_a_report_and_applies_gates(tmp_path):
    gates = tmp_path / "gates.yaml"
    gates.write_text("min:\n  routing_accuracy: 0.5\n", encoding="utf-8")
    code = main(
        ["--cases", "case_013", "case_018", "--out", str(tmp_path), "--thresholds", str(gates)],
        provider=FakeProvider(perfect_model),
    )
    assert code == 0
    (report,) = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert {p.name for p in report.iterdir()} == {"cases.csv", "metrics.json", "summary.md"}
    metrics = json.loads((report / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["metrics"]["routing_accuracy"] == 1.0
    assert set(metrics["meta"]["prompt_versions"]) == {"extract", "classify", "summarize"}
    assert "Routing accuracy" in (report / "summary.md").read_text(encoding="utf-8")


def broken_model(system, prompt, schema):
    """Like perfect_model, but always invents a wrong policy number."""
    answer = json.loads(perfect_model(system, prompt, schema))
    if "multiple_claims" in schema["properties"]:
        answer["policy_number"] = "POL-INVENTED"
    return json.dumps(answer)


def test_regression_check_catches_a_worse_run(tmp_path):
    from evals.regression import main as regression_main

    no_gates = tmp_path / "none.yaml"
    for label, model in (("a_good", perfect_model), ("b_broken", broken_model)):
        main(
            [
                "--cases",
                "case_013",
                "case_018",
                "--out",
                str(tmp_path / "reports"),
                "--thresholds",
                str(no_gates),
                "--label",
                label,
            ],
            provider=FakeProvider(model),
        )
    saved = tmp_path / "regression.md"
    code = regression_main(
        ["--reports", str(tmp_path / "reports"), "--split", "custom", "--save", str(saved)]
    )
    assert code == 1
    text = saved.read_text(encoding="utf-8")
    assert "routing_accuracy" in text and "WORSE" in text
    assert "case_013: now WRONG" in text


def test_main_fails_when_a_gate_is_missed(tmp_path):
    gates = tmp_path / "gates.yaml"
    gates.write_text("max:\n  latency_p95_s: 0.0\n", encoding="utf-8")
    code = main(
        ["--cases", "case_013", "--out", str(tmp_path), "--thresholds", str(gates)],
        provider=FakeProvider(perfect_model),
    )
    assert code == 1
