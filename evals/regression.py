"""Compare the latest evaluation report with the previous one and flag what got worse.

Usage:
  .venv\\Scripts\\python -m evals.regression                    (two latest dev reports)
  .venv\\Scripts\\python -m evals.regression --before A --after B --save reports\\regression.md
Exit code 1 when any metric got worse beyond its tolerance.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from triage.config import REPO_ROOT

HIGHER_IS_BETTER = ("routing_accuracy", "classification_", "field_accuracy_", "pii_recall")
LOWER_IS_BETTER_RATES = ("retry_rate", "summary_warning_rate")
LOWER_IS_BETTER_RELATIVE = ("latency_", "tokens_")


@dataclass(frozen=True)
class Regression:
    metric: str
    before: float
    after: float


def direction(metric: str) -> str | None:
    if metric.startswith(HIGHER_IS_BETTER):
        return "higher"
    if metric.startswith(LOWER_IS_BETTER_RATES) or metric == "n_errors":
        return "lower_abs"
    if metric.startswith(LOWER_IS_BETTER_RELATIVE):
        return "lower_rel"
    return None


def compare(
    before: dict[str, Any], after: dict[str, Any], abs_tol: float = 0.02, rel_tol: float = 0.2
) -> list[Regression]:
    """abs_tol: allowed drop in a rate (one case in 30 is 0.033). rel_tol: allowed slowdown."""
    found = []
    for metric, old in before.items():
        new = after.get(metric)
        if old is None or new is None or not isinstance(old, int | float):
            continue
        kind = direction(metric)
        worse = (
            (kind == "higher" and new < old - abs_tol)
            or (kind == "lower_abs" and new > old + abs_tol)
            or (kind == "lower_rel" and new > old * (1 + rel_tol))
        )
        if worse:
            found.append(Regression(metric, old, new))
    return found


def load(folder: Path) -> dict[str, Any]:
    return json.loads((folder / "metrics.json").read_text(encoding="utf-8"))


def latest_two(reports: Path, split: str) -> tuple[Path, Path]:
    folders = sorted(
        f
        for f in reports.iterdir()
        if (f / "metrics.json").exists() and load(f)["meta"]["split"] == split
    )
    if len(folders) < 2:
        raise SystemExit(f"need two {split} reports in {reports}, found {len(folders)}")
    return folders[-2], folders[-1]


def case_changes(before: Path, after: Path) -> list[str]:
    old = pd.read_csv(before / "cases.csv").set_index("case_id")
    new = pd.read_csv(after / "cases.csv").set_index("case_id")
    lines = []
    for case_id in old.index.intersection(new.index):
        was, now = bool(old.at[case_id, "queue_correct"]), bool(new.at[case_id, "queue_correct"])
        if was != now:
            verdict = "now WRONG" if was else "now right"
            lines.append(
                f"- {case_id}: {verdict} (queue {old.at[case_id, 'queue']} -> {new.at[case_id, 'queue']},"
                f" expected {new.at[case_id, 'expected_queue']})"
            )
    return lines


def report(before: Path, after: Path) -> tuple[str, list[Regression]]:
    old, new = load(before), load(after)
    regressions = compare(old["metrics"], new["metrics"])
    flagged = {r.metric for r in regressions}
    lines = [
        f"# Regression check: {after.name} vs {before.name}",
        "",
        f"- Before: {before.name}, prompts {old['meta']['prompt_versions']}",
        f"- After: {after.name}, prompts {new['meta']['prompt_versions']}",
        "",
        "| Metric | Before | After | Verdict |",
        "|---|---|---|---|",
    ]
    for metric, value in new["metrics"].items():
        if direction(metric) and metric in old["metrics"]:
            verdict = "WORSE" if metric in flagged else ""
            lines.append(f"| {metric} | {old['metrics'][metric]} | {value} | {verdict} |")
    changes = case_changes(before, after)
    lines += ["", f"## Cases whose routing changed ({len(changes)})", "", *(changes or ["- none"])]
    lines += [
        "",
        f"**Result: {len(regressions)} metrics got worse.**"
        if regressions
        else "**Result: no regressions.**",
    ]
    return "\n".join(lines) + "\n", regressions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flag metrics that got worse between two runs.")
    parser.add_argument("--reports", type=Path, default=REPO_ROOT / "reports")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--save", type=Path, help="also write the result as markdown")
    args = parser.parse_args(argv)

    before, after = (
        (args.before, args.after)
        if args.before and args.after
        else latest_two(args.reports, args.split)
    )
    text, regressions = report(before, after)
    print(text)
    if args.save:
        args.save.write_text(text, encoding="utf-8")
    return 1 if regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
