"""Triage one claim PDF from the command line.

Usage: python -m triage.cli path\\to\\claim.pdf [--json]
Exit codes: 0 completed, 2 rejected (unreadable file).
"""

import argparse
import sys
from pathlib import Path

from triage.config import Settings
from triage.graph import run_triage
from triage.llm import LLMProvider, make_provider
from triage.schemas import TriageResult


def render(result: TriageResult) -> str:
    lines = [f"Request {result.request_id}: {result.status}"]
    if result.status == "rejected":
        lines.append(f"Reason: {result.rejection_reason}")
    else:
        lines.append(f"Queue:    {result.queue} ({'; '.join(result.reasons)})")
        lines.append(f"Category: {result.category} (confidence {result.confidence:.2f})")
        lines.append(f"Extraction attempts: {result.extraction_attempts}")
        lines.append("Fields:")
        for name, value in result.fields.model_dump(exclude={"loss_description"}).items():
            lines.append(f"  {name:21} {value}")
        if result.missing_fields:
            lines.append(f"Missing:  {', '.join(result.missing_fields)}")
        lines.append(f"Summary:  {result.summary}")
        for warning in result.warnings:
            lines.append(f"Warning:  {warning}")
    lines.append("Steps:")
    for step in result.trace:
        tokens = f", {step.prompt_tokens}+{step.output_tokens} tokens" if step.prompt_tokens else ""
        lines.append(f"  {step.node:12} {step.latency_s:7.2f}s{tokens}  {step.outcome}")
    total = sum(step.latency_s for step in result.trace)
    lines.append(f"Total {total:.1f}s")
    return "\n".join(lines)


def main(argv: list[str] | None = None, provider: LLMProvider | None = None) -> int:
    parser = argparse.ArgumentParser(description="Triage one insurance claim PDF.")
    parser.add_argument("pdf", type=Path, help="path to a claim PDF")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args(argv)

    result = run_triage(args.pdf.read_bytes(), provider or make_provider(Settings()))
    print(result.model_dump_json(indent=2) if args.json else render(result))
    return 0 if result.status == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
