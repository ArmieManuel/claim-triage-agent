# Evaluation report 20261026-134704_dev_baseline

| Run detail | Value |
|---|---|
| timestamp | 20261026-134704 |
| split | dev |
| label | baseline |
| n_cases | 30 |
| model | gemma4:e2b |
| git_commit | 7a267e7 |
| git_dirty | False |
| prompt_versions | extract=extract-v1, classify=classify-v1, summarize=summarize-v1 |

## Key metrics

| Metric | Value |
|---|---|
| Routing accuracy | 0.9667 |
| Routing accuracy, normal cases | 1.0 |
| Routing accuracy, hard cases | 0.8333 |
| Classification accuracy | 1.0 |
| Classification macro F1 | 1.0 |
| Field accuracy, mean over fields | 0.9958 |
| Human review rate | 0.1 |
| Human review rate, expected | 0.1333 |
| Retry rate | 0.0 |
| Latency p50 (s) | 27.62 |
| Latency p95 (s) | 36.13 |
| Prompt tokens per case | 1807.7 |
| Output tokens per case | 339.4 |
| Tokens, total | 64412 |
| PII redaction recall | 1.0 |
| Summary warning rate | 0.0 |
| Errors | 0 |

## Field accuracy

| Field | Accuracy |
|---|---|
| claim_number | 1.0 |
| policy_number | 1.0 |
| date_of_loss | 0.9667 |
| claimant_role | 1.0 |
| amount_claimed | 1.0 |
| location | 1.0 |
| policy_start_date | 1.0 |
| police_report_number | 1.0 |

## Quality gates

- All gates passed.

## Wrongly routed cases (1)

| Case | Tags | Expected | Got | Category | Confidence | Reasons |
|---|---|---|---|---|---|---|
| case_030 | ambiguous_category | human_review | standard_handler | property_fire | 0.95 | no special rule applies |
