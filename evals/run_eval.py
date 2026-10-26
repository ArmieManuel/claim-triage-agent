"""Run the agent over golden cases and write a timestamped report to reports/.

Usage:
  .venv\\Scripts\\python -m evals.run_eval                 (dev split, the default)
  .venv\\Scripts\\python -m evals.run_eval --split holdout  (once per milestone, never tune on it)
  .venv\\Scripts\\python -m evals.run_eval --cases case_013 case_030 --label quick
Exit code 1 when a quality gate in evals/thresholds.yaml is missed.
"""

import argparse
import json
import re
import subprocess
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from evals.metrics import check_thresholds, score_case, summarize_metrics
from triage.config import REPO_ROOT, Settings
from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.graph import run_triage
from triage.llm import LLMProvider, make_provider
from triage.llm.replay import RecordingProvider
from triage.nodes.ingest import ingest
from triage.pii import redact
from triage.schemas import GoldenCase

DEFAULT_THRESHOLDS = REPO_ROOT / "evals" / "thresholds.yaml"
DEFAULT_REPORTS = REPO_ROOT / "reports"

LABELS = {
    "routing_accuracy": "Routing accuracy",
    "routing_accuracy_normal": "Routing accuracy, normal cases",
    "routing_accuracy_hard": "Routing accuracy, hard cases",
    "classification_accuracy": "Classification accuracy",
    "classification_macro_f1": "Classification macro F1",
    "field_accuracy_mean": "Field accuracy, mean over fields",
    "human_review_rate": "Human review rate",
    "expected_human_review_rate": "Human review rate, expected",
    "retry_rate": "Retry rate",
    "latency_p50_s": "Latency p50 (s)",
    "latency_p95_s": "Latency p95 (s)",
    "tokens_prompt_mean": "Prompt tokens per case",
    "tokens_output_mean": "Output tokens per case",
    "tokens_total": "Tokens, total",
    "pii_recall": "PII redaction recall",
    "summary_warning_rate": "Summary warning rate",
    "n_errors": "Errors",
}


def pii_recall(case: GoldenCase) -> float:
    """Share of the planted personal values that redaction removed."""
    text = ingest((GOLDEN_DIR / case.split / case.pdf_file).read_bytes()).text
    redacted = re.sub(r"\s+", " ", redact(text).text)
    hidden = [re.sub(r"\s+", " ", p.value) not in redacted for p in case.pii]
    return sum(hidden) / len(hidden) if hidden else 1.0


def evaluate(
    cases: list[GoldenCase], provider: LLMProvider, today: date | None = None, verbose: bool = False
) -> pd.DataFrame:
    rows = []
    for number, case in enumerate(cases, start=1):
        pdf = (GOLDEN_DIR / case.split / case.pdf_file).read_bytes()
        started = time.perf_counter()
        result, error = None, ""
        try:
            result = run_triage(pdf, provider, today=today)
        except Exception as exc:  # one broken case must not stop the run
            error = f"{type(exc).__name__}: {exc}"
        row = score_case(case, result, time.perf_counter() - started, pii_recall(case), error)
        row["prompt_versions"] = json.dumps(result.prompt_versions if result else {})
        rows.append(row)
        if verbose:
            mark = "ok" if row["queue_correct"] else "XX"
            print(
                f"[{number}/{len(cases)}] {case.case_id} {mark} {row['latency_s']:6.1f}s "
                f"queue {row['queue'] or row['status']} (expected {row['expected_queue']})",
                flush=True,
            )
    return pd.DataFrame(rows)


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _summary_markdown(
    name: str, meta: dict[str, Any], metrics: dict[str, Any], df: pd.DataFrame, failures: list[str]
) -> str:
    lines = [f"# Evaluation report {name}", ""]
    lines += ["| Run detail | Value |", "|---|---|"]
    for key in ("timestamp", "split", "label", "n_cases", "model", "git_commit", "git_dirty"):
        lines.append(f"| {key} | {meta.get(key)} |")
    lines.append(
        f"| prompt_versions | {', '.join(f'{k}={v}' for k, v in meta['prompt_versions'].items())} |"
    )
    lines += ["", "## Key metrics", "", "| Metric | Value |", "|---|---|"]
    for key, label in LABELS.items():
        lines.append(f"| {label} | {metrics.get(key)} |")
    lines += ["", "## Field accuracy", "", "| Field | Accuracy |", "|---|---|"]
    for key, value in metrics.items():
        if key.startswith("field_accuracy_") and key != "field_accuracy_mean":
            lines.append(f"| {key.removeprefix('field_accuracy_')} | {value} |")
    lines += ["", "## Quality gates", ""]
    lines += [f"- FAILED: {f}" for f in failures] or ["- All gates passed."]
    wrong = df[~df["queue_correct"]]
    lines += ["", f"## Wrongly routed cases ({len(wrong)})", ""]
    if len(wrong):
        lines += [
            "| Case | Tags | Expected | Got | Category | Confidence | Reasons |",
            "|---|---|---|---|---|---|---|",
        ]
        for _, r in wrong.iterrows():
            lines.append(
                f"| {r.case_id} | {r.tags} | {r.expected_queue} | {r.queue or r.status} | "
                f"{r.category} | {r.confidence} | {r.reasons or r.error} |"
            )
    return "\n".join(lines) + "\n"


def write_report(
    df: pd.DataFrame, metrics: dict[str, Any], meta: dict[str, Any], failures: list[str], out: Path
) -> Path:
    name = f"{meta['timestamp']}_{meta['split']}" + (f"_{meta['label']}" if meta["label"] else "")
    folder = out / name
    folder.mkdir(parents=True, exist_ok=False)
    df.to_csv(folder / "cases.csv", index=False)
    payload = {"meta": meta, "metrics": metrics, "gates": {"failures": failures}}
    (folder / "metrics.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (folder / "summary.md").write_text(
        _summary_markdown(name, meta, metrics, df, failures), encoding="utf-8"
    )
    return folder


def main(argv: list[str] | None = None, provider: LLMProvider | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the triage agent on golden cases.")
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    parser.add_argument("--cases", nargs="+", help="only these case ids")
    parser.add_argument("--limit", type=int, help="only the first N cases")
    parser.add_argument("--label", default="", help="short tag added to the report folder name")
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument(
        "--record", type=Path, help="save every model answer to this cassette for later replay"
    )
    args = parser.parse_args(argv)

    cases = load_golden_cases(split=None if args.split == "all" else args.split)
    split = args.split
    if args.cases:
        cases = [c for c in load_golden_cases() if c.case_id in set(args.cases)]
        split = "custom"
    if args.limit:
        cases = cases[: args.limit]

    settings = Settings()
    provider = provider or make_provider(settings)
    model_name = getattr(provider, "model", type(provider).__name__)
    if args.record:
        provider = RecordingProvider(provider)
    df = evaluate(cases, provider, verbose=True)
    if args.record:
        provider.save(args.record)
        print(f"Recorded {len(provider.recorded)} model answers to {args.record}")
    metrics = summarize_metrics(df)
    versions = Counter(df["prompt_versions"]).most_common(1)[0][0] if len(df) else "{}"
    meta = {
        "timestamp": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "split": split,
        "label": re.sub(r"[^\w-]", "-", args.label),
        "n_cases": len(cases),
        "model": model_name,
        "prompt_versions": json.loads(versions),
        "git_commit": _git("rev-parse", "--short", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "thresholds": str(args.thresholds),
    }
    gates = (
        yaml.safe_load(args.thresholds.read_text(encoding="utf-8"))
        if args.thresholds.exists()
        else {}
    )
    failures = check_thresholds(metrics, gates or {})
    folder = write_report(df, metrics, meta, failures, args.out)

    print(f"\nReport: {folder}")
    for key in (
        "routing_accuracy",
        "classification_accuracy",
        "field_accuracy_mean",
        "pii_recall",
        "latency_p50_s",
        "latency_p95_s",
    ):
        print(f"  {LABELS[key]:34} {metrics[key]}")
    for failure in failures:
        print(f"  GATE FAILED: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
