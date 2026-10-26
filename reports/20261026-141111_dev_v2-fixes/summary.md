# Evaluation report 20261026-141111_dev_v2-fixes

| Run detail | Value |
|---|---|
| timestamp | 20261026-141111 |
| split | dev |
| label | v2-fixes |
| n_cases | 30 |
| model | gemma4:e2b |
| git_commit | 2676add |
| git_dirty | False |
| prompt_versions | extract=extract-v2, classify=classify-v2, summarize=summarize-v1 |

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
| Latency p50 (s) | 31.66 |
| Latency p95 (s) | 84.69 |
| Prompt tokens per case | 1884.1 |
| Output tokens per case | 349.2 |
| Tokens, total | 66999 |
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
| police_report_number | 0.9333 |

## Quality gates

- FAILED: latency_p95_s = 84.69, gate allows at most 60

## Wrongly routed cases (0)

