# Evaluation reports

Every folder is one run of `python -m evals.run_eval`, named `<timestamp>_<split>_<label>`. Reports are committed, and every metric in the README must come from one of them.

Each folder holds:

- `summary.md`: run details (git commit, model, prompt versions), key metrics, field accuracy, gate results and every wrongly routed case
- `metrics.json`: the same numbers for scripts, used by `python -m evals.regression`
- `cases.csv`: one row per case with expected and predicted values, latency and tokens

Splits: `dev` is used for tuning. `holdout` is run once per milestone and never tuned against.
