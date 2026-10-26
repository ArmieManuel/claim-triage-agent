"""Run the triage agent on one golden case with the real local model and compare.

Usage: .venv\\Scripts\\python scripts\\try_one_claim.py case_013
A manual sanity check, not an evaluation. Phase 4 measures quality on the whole golden set.
"""

import sys

from triage.cli import render
from triage.config import Settings
from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.graph import run_triage
from triage.llm import make_provider

COMPARED = (
    "claim_number",
    "policy_number",
    "date_of_loss",
    "claimant_role",
    "amount_claimed",
    "location",
    "policy_start_date",
    "police_report_number",
)


def main(case_id: str) -> None:
    case = next(c for c in load_golden_cases() if c.case_id == case_id)
    print(f"Case {case.case_id} ({case.country}, {case.layout}, tags {case.tags or 'none'})\n")
    result = run_triage(
        (GOLDEN_DIR / case.split / case.pdf_file).read_bytes(), make_provider(Settings())
    )
    print(render(result))
    if result.status != "completed":
        return

    expected = case.expected
    print("\nCompared with the expected answer:")
    if result.fields:
        for name in COMPARED:
            got, want = getattr(result.fields, name), getattr(expected.fields, name)
            print(f"  {'ok' if got == want else 'XX'} {name:21} {got!s:28} expected {want}")
    category_ok = result.category in expected.acceptable_categories
    print(
        f"  {'ok' if category_ok else 'XX'} category              {result.category!s:28} expected {expected.category}"
    )
    route_ok = result.queue == expected.route
    print(
        f"  {'ok' if route_ok else 'XX'} queue                 {result.queue!s:28} expected {expected.route}"
    )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "case_013")
