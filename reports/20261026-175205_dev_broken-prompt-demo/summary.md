# Evaluation report 20261026-175205_dev_broken-prompt-demo

| Run detail | Value |
|---|---|
| timestamp | 20261026-175205 |
| split | dev |
| label | broken-prompt-demo |
| n_cases | 30 |
| model | gemma4:e2b |
| git_commit | f627777 |
| git_dirty | True |
| prompt_versions | extract=extract-v3-broken-demo, classify=classify-v2, summarize=summarize-v1 |

## Key metrics

| Metric | Value |
|---|---|
| Routing accuracy | 1.0 |
| Routing accuracy, normal cases | 1.0 |
| Routing accuracy, hard cases | 1.0 |
| Classification accuracy | 1.0 |
| Classification macro F1 | 1.0 |
| Field accuracy, mean over fields | 0.9917 |
| Human review rate | 0.1333 |
| Human review rate, expected | 0.1333 |
| Retry rate | 0.0 |
| Latency p50 (s) | 23.67 |
| Latency p95 (s) | 30.69 |
| Prompt tokens per case | 1914.7 |
| Output tokens per case | 349.9 |
| Tokens, total | 67936 |
| PII redaction recall | 1.0 |
| Summary warning rate | 0.0333 |
| Errors | 0 |

## Field accuracy

| Field | Accuracy |
|---|---|
| claim_number | 1.0 |
| policy_number | 1.0 |
| date_of_loss | 0.9333 |
| claimant_role | 1.0 |
| amount_claimed | 1.0 |
| location | 1.0 |
| policy_start_date | 1.0 |
| police_report_number | 1.0 |

## Quality gates

- All gates passed.

## Wrongly routed cases (0)

