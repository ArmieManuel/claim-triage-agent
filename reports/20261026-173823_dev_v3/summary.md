# Evaluation report 20261026-173823_dev_v3

| Run detail | Value |
|---|---|
| timestamp | 20261026-173823 |
| split | dev |
| label | v3 |
| n_cases | 30 |
| model | gemma4:e2b |
| git_commit | 03c0865 |
| git_dirty | False |
| prompt_versions | extract=extract-v3, classify=classify-v2, summarize=summarize-v1 |

## Key metrics

| Metric | Value |
|---|---|
| Routing accuracy | 1.0 |
| Routing accuracy, normal cases | 1.0 |
| Routing accuracy, hard cases | 1.0 |
| Classification accuracy | 1.0 |
| Classification macro F1 | 1.0 |
| Field accuracy, mean over fields | 1.0 |
| Human review rate | 0.1333 |
| Human review rate, expected | 0.1333 |
| Retry rate | 0.0 |
| Latency p50 (s) | 27.36 |
| Latency p95 (s) | 43.2 |
| Prompt tokens per case | 1917.7 |
| Output tokens per case | 349.1 |
| Tokens, total | 68003 |
| PII redaction recall | 1.0 |
| Summary warning rate | 0.0 |
| Errors | 0 |

## Field accuracy

| Field | Accuracy |
|---|---|
| claim_number | 1.0 |
| policy_number | 1.0 |
| date_of_loss | 1.0 |
| claimant_role | 1.0 |
| amount_claimed | 1.0 |
| location | 1.0 |
| policy_start_date | 1.0 |
| police_report_number | 1.0 |

## Quality gates

- All gates passed.

## Wrongly routed cases (0)

