# Golden dataset

50 synthetic claim PDFs, each with an expected JSON file (`GoldenCase` in `src/triage/schemas.py`). Every person, address, phone number, email, NI number, vehicle registration and insurer is fake. Each PDF carries a "SYNTHETIC TEST DOCUMENT" footer.

| Split | Cases | Hard cases | Use |
|---|---|---|---|
| `dev/` | 30 | 6 | Prompt tuning and debugging |
| `holdout/` | 20 | 4 | Reported once per milestone. Never tune against it |

## What each JSON holds

- `expected.fields`: the claim fields, with `null` where the document does not state a value.
- `expected.category`, plus `acceptable_categories` for deliberately ambiguous cases.
- `expected.route`: the target queue under [docs/routing_policy.md](../../docs/routing_policy.md).
- `expected.multiple_claims`: true when one document holds two claims.
- `pii`: every personal value planted in the PDF, used to test redaction.
- `tags`, `layout` and `hard` for slicing evaluation results.

## Variation

- Layouts: claim form (tables in shuffled order), letter, and printed email.
- Labels, role wording, amount formats and date formats vary per case.
- Normal cases cover all six categories and four queues (auto, standard, senior, fraud).
- Hard cases: missing policy number, amount or date; ambiguous category (water or fire, theft or collision); two claims in one email; unusual date formats; and two long descriptions (about 2,400 and 3,300 words), one with the amount stated only inside the narrative.

## Regenerating

```
.venv\Scripts\python -m generator.build_golden
```

Output is deterministic for the pinned Faker and ReportLab versions. `tests/unit/test_golden_dataset.py` fails if the committed files drift from the generator, so regenerate after any generator change and commit the result.
