"""Run the Phase 2 nodes by hand on one golden case with the real local model.

Usage: .venv\\Scripts\\python scripts\\try_one_claim.py case_013
This is a manual check, not an evaluation. Phase 3 wires the nodes into a graph,
and Phase 4 measures quality over the whole golden set.
"""

import sys
import time

from triage.config import Settings
from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.llm import make_provider
from triage.nodes.classify import classify
from triage.nodes.extract import extract
from triage.nodes.ingest import ingest
from triage.nodes.summarize import summarize
from triage.nodes.validate import validate
from triage.pii import redact, restore
from triage.rules import load_routing_policy, route

MAX_RETRIES = 2


def main(case_id: str) -> None:
    case = next(c for c in load_golden_cases() if c.case_id == case_id)
    provider = make_provider(Settings())
    started = time.perf_counter()

    text = ingest((GOLDEN_DIR / case.split / case.pdf_file).read_bytes()).text
    redaction = redact(text)
    print(f"Case {case.case_id} ({case.country}, {case.layout}, tags {case.tags or 'none'})")
    print(f"Redacted {len(redaction.mapping)} personal values: {sorted(redaction.mapping)}")

    feedback: list[str] | None = None
    for attempt_number in range(1, MAX_RETRIES + 2):
        attempt = extract(redaction.text, provider, feedback)
        if attempt.output is None:
            feedback = [attempt.error]
            print(f"Extract attempt {attempt_number}: {attempt.error}")
            continue
        result = validate(attempt.output, redaction.text)
        print(
            f"Extract attempt {attempt_number}: {attempt.response.latency_s:.1f}s, "
            f"{attempt.response.prompt_tokens}+{attempt.response.output_tokens} tokens, "
            f"errors {result.errors or 'none'}"
        )
        if result.ok:
            break
        feedback = result.errors
    failed = attempt.output is None or not result.ok

    cls = classify(redaction.text, provider)
    print(f"Classify: {cls.category} ({cls.confidence:.2f}) {cls.reason}")

    fields = result.fields if attempt.output else None
    decision = route(
        fields,
        category=cls.category,
        confidence=cls.confidence,
        multiple_claims=result.multiple_claims if attempt.output else False,
        missing=result.missing if attempt.output else [],
        policy=load_routing_policy(),
        extraction_failed=failed,
    )
    summary = summarize(redaction.text, fields, cls.category, decision.queue, provider)

    expected = case.expected
    print("\nField              extracted                      expected")
    for name in (
        "claim_number",
        "policy_number",
        "date_of_loss",
        "claimant_role",
        "amount_claimed",
        "location",
        "policy_start_date",
        "police_report_number",
    ):
        got, want = getattr(fields, name), getattr(expected.fields, name)
        mark = "ok " if got == want else "XX "
        print(f"{mark}{name:17} {got!s:30} {want}")
    print(f"\nCategory {cls.category} (expected {expected.category})")
    print(f"Route    {decision.queue} (expected {expected.route}) because {decision.reasons}")
    print(
        f"\nSummary ({summary.sentence_count} sentences, ungrounded numbers "
        f"{summary.ungrounded_numbers or 'none'}):"
    )
    print(restore(summary.summary, redaction.mapping))
    print(f"\nTotal time {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "case_013")
