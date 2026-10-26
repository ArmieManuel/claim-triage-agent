# Evaluation report 20261026-184903_custom_ci-cassette

| Run detail | Value |
|---|---|
| timestamp | 20261026-184903 |
| split | custom |
| label | ci-cassette |
| n_cases | 10 |
| model | gemma4:e2b |
| git_commit | 63e576f |
| git_dirty | True |
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
| Human review rate | 0.3 |
| Human review rate, expected | 0.3 |
| Retry rate | 0.0 |
| Latency p50 (s) | 29.21 |
| Latency p95 (s) | 31.29 |
| Prompt tokens per case | 1645.0 |
| Output tokens per case | 354.7 |
| Tokens, total | 19997 |
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

