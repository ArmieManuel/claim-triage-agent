# Evaluation report 20261026-181213_holdout_milestone-phase4

| Run detail | Value |
|---|---|
| timestamp | 20261026-181213 |
| split | holdout |
| label | milestone-phase4 |
| n_cases | 20 |
| model | gemma4:e2b |
| git_commit | 0f0a4b1 |
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
| Field accuracy, mean over fields | 0.9875 |
| Human review rate | 0.1 |
| Human review rate, expected | 0.1 |
| Retry rate | 0.0 |
| Latency p50 (s) | 32.78 |
| Latency p95 (s) | 48.11 |
| Prompt tokens per case | 2209.5 |
| Output tokens per case | 348.6 |
| Tokens, total | 51162 |
| PII redaction recall | 1.0 |
| Summary warning rate | 0.0 |
| Errors | 0 |

## Field accuracy

| Field | Accuracy |
|---|---|
| claim_number | 1.0 |
| policy_number | 1.0 |
| date_of_loss | 1.0 |
| claimant_role | 0.95 |
| amount_claimed | 1.0 |
| location | 1.0 |
| policy_start_date | 1.0 |
| police_report_number | 0.95 |

## Quality gates

- All gates passed.

## Wrongly routed cases (0)

