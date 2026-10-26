# Deliberate regression demo (PLAN.md Phase 4 acceptance)

This run used a prompt that was broken on purpose. It was never committed as the real prompt and was reverted right after the run.

## The change

`src/triage/prompts/extract.yaml`, labelled `extract-v3-broken-demo`, replaced the date rule

> The date of loss is when the incident happened, not when the letter, email or form was sent.

with

> The date of loss is the date the letter, email or form was sent or completed.

This is a hard mistake to catch in code: the wrong date is written in the document, so the date grounding check in `validate.py` accepts it.

## What caught it

`python -m evals.regression --split dev` compared this run with the previous dev run (`20261026-173823_dev_v3`) and exited with code 1. Full output: [regression_vs_v3.md](regression_vs_v3.md).

| Metric | v3 | Broken prompt | Verdict |
|---|---|---|---|
| field_accuracy_date_of_loss | 1.0 | 0.9333 | WORSE |
| summary_warning_rate | 0.0 | 0.0333 | WORSE |

Wrong dates, read from `cases.csv`:

| Case | Layout | Expected | Predicted | What the model took |
|---|---|---|---|---|
| case_001 | email | 2026-04-24 | 2026-04-27 | the `Sent:` date |
| case_029 | form | 2025-10-24 | 2025-10-31 | the `Form completed on` date |

## What it shows

- The quality gates in `evals/thresholds.yaml` all passed (mean field accuracy 0.992 is above the 0.95 gate), so a gate alone would have let this change through.
- The regression check compares each run with the previous one and flags any metric that got worse beyond its tolerance, so it caught a two-case drop in one field.
- The model followed the bad rule in only 2 of 30 cases, because labels like "Date of incident" still guided it. Small prompt changes can have small effects that are easy to miss without a run-to-run comparison.
