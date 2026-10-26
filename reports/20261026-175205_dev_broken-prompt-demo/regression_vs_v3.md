# Regression check: 20261026-175205_dev_broken-prompt-demo vs 20261026-173823_dev_v3

- Before: 20261026-173823_dev_v3, prompts {'extract': 'extract-v3', 'classify': 'classify-v2', 'summarize': 'summarize-v1'}
- After: 20261026-175205_dev_broken-prompt-demo, prompts {'extract': 'extract-v3-broken-demo', 'classify': 'classify-v2', 'summarize': 'summarize-v1'}

| Metric | Before | After | Verdict |
|---|---|---|---|
| n_errors | 0 | 0 |  |
| routing_accuracy | 1.0 | 1.0 |  |
| routing_accuracy_normal | 1.0 | 1.0 |  |
| routing_accuracy_hard | 1.0 | 1.0 |  |
| classification_accuracy | 1.0 | 1.0 |  |
| classification_macro_f1 | 1.0 | 1.0 |  |
| field_accuracy_claim_number | 1.0 | 1.0 |  |
| field_accuracy_policy_number | 1.0 | 1.0 |  |
| field_accuracy_date_of_loss | 1.0 | 0.9333 | WORSE |
| field_accuracy_claimant_role | 1.0 | 1.0 |  |
| field_accuracy_amount_claimed | 1.0 | 1.0 |  |
| field_accuracy_location | 1.0 | 1.0 |  |
| field_accuracy_policy_start_date | 1.0 | 1.0 |  |
| field_accuracy_police_report_number | 1.0 | 1.0 |  |
| field_accuracy_mean | 1.0 | 0.9917 |  |
| retry_rate | 0.0 | 0.0 |  |
| latency_p50_s | 27.36 | 23.67 |  |
| latency_p95_s | 43.2 | 30.69 |  |
| latency_mean_s | 31.79 | 26.21 |  |
| tokens_prompt_mean | 1917.7 | 1914.7 |  |
| tokens_output_mean | 349.1 | 349.9 |  |
| tokens_total | 68003 | 67936 |  |
| pii_recall | 1.0 | 1.0 |  |
| summary_warning_rate | 0.0 | 0.0333 | WORSE |

## Cases whose routing changed (0)

- none

**Result: 2 metrics got worse.**
