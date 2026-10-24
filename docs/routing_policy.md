# Routing policy

Plain rules, applied in order. The first rule that matches decides the queue. Thresholds live in [config/routing.yaml](../config/routing.yaml) so they can change without touching code or prompts.

| Order | Rule | Queue |
|---|---|---|
| 1 | A required field is missing, the document holds more than one claim, or the category is ambiguous or low confidence | `human_review` |
| 2 | Loss happened within 30 days of the policy start date, or a motor theft has no police report number | `fraud_review` |
| 3 | Amount claimed is above 25,000 GBP, or the category is `liability` | `senior_handler` |
| 4 | Amount claimed is 2,500 GBP or less, and the category is not `motor_theft` or `liability` | `auto_process` |
| 5 | Everything else | `standard_handler` |

Required fields: claim number, policy number, date of loss, claimant role, amount claimed, loss description and location. Policy start date and police report number are optional.

These rules are synthetic and exist to make routing testable. They are not taken from any real insurer.

## How the golden dataset uses this

Each golden case is designed for one target queue, and the generator picks amounts, dates and police references that put the case in that queue under these rules. `tests/unit/test_generator.py` checks every ground-truth route against the rules, so the expected answers cannot drift from the policy.
