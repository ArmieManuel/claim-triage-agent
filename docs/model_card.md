# Model card

Status: complete through Phase 8. Evaluation sections are filled in only from real runs saved under `reports/`. Privacy, retention and GDPR notes: [privacy_and_governance.md](privacy_and_governance.md). System design: [architecture.md](architecture.md).

CI does not run this model. It replays answers recorded from it on ten dev cases (`evals/cassettes/ci_subset.json`, recording run `reports/20261026-184903_custom_ci-cassette`: routing, classification and field accuracy all 1.0), so every push runs the full graph and the quality gates without a model.

## Model

| Item | Value |
|---|---|
| Runtime | Ollama 0.40.9 (Windows), local server at `http://localhost:11434` |
| Model | `gemma4:e2b` (Google Gemma 4, 2.3B effective parameters, 5.1B with embeddings) |
| Ollama model id | `b37049369adf` |
| Download size | 4.6 GB |
| Context window | 128K supported. Ollama default is 4096 tokens, so the provider sets `num_ctx` explicitly |
| Memory while loaded | about 1.1 GB at the default 4096 context (from `ollama ps`) |
| Compute | 100% CPU. Ollama detects the Intel Iris Xe iGPU over Vulkan but drops integrated GPUs by default |

## Development hardware

Lenovo Yoga Slim 7 Pro 14IHU5 O (82NH): Intel Core i5-11320H (4 cores, 8 threads), 16 GB RAM, Intel Iris Xe graphics, Windows 11 Home.

## Why this model

- Fits next to PyCharm and a browser in 16 GB RAM, unlike 7B and larger models.
- Runs locally for free, matching the local-first rule in PLAN.md.
- Supports schema-constrained output through Ollama's `format` parameter. Ollama documents that schema-enforced structured outputs are not available on its cloud models, which is one more reason to stay local.

## Setup smoke test (not an evaluation result)

One hand-written synthetic claim sentence, schema-constrained extraction of four fields, `temperature` 0, thinking off, run on 2026-10-23:

- Cold call 17.4 s (11.5 s model load), warm call 4.0 s.
- 195 prompt tokens, 58 output tokens, about 33 generated tokens per second.
- All four fields correct. The date came back as written ("3 March 2026"), so the validate node must normalize dates.

This is a single sanity check, not a measured quality figure.

## Intended use

Triage of synthetic, text-based English motor and property claim PDFs from claimants in Germany, Italy and Austria, with amounts in euros, for a portfolio project. Not for real claims or real personal data.

## Evaluation results

All numbers come from committed reports in `reports/`. Golden set: 50 synthetic claims, 30 dev (used for tuning) and 20 holdout (run once, never tuned against), 10 of them hard cases. Prompts: `extract-v3`, `classify-v2`, `summarize-v1`.

| Metric | Dev, v3 (30 cases) | Holdout (20 cases) |
|---|---|---|
| Routing accuracy | 1.00 | **1.00** |
| Routing accuracy, hard cases | 1.00 (6/6) | **1.00** (4/4) |
| Classification accuracy and macro F1 | 1.00 | **1.00** |
| Field accuracy, mean over 8 fields | 1.00 | **0.988** |
| PII redaction recall | 1.00 | **1.00** |
| Human review rate (expected) | 0.133 (0.133) | 0.10 (0.10) |
| Retry rate | 0.0 | 0.0 |
| Latency p50 / p95 | 27.4 s / 43.2 s | **32.8 s / 48.1 s** |
| Tokens per case, in / out | 1918 / 349 | 2210 / 349 |

Reports: dev `20261026-173823_dev_v3`, holdout `20261026-181213_holdout_milestone-phase4`.

How the dev numbers got there (each step is a committed report):

| Run | Change | Routing | Fields | Note |
|---|---|---|---|---|
| Baseline | v1 prompts | 0.967 | 0.996 | case_030 ambiguous claim at confidence 0.95; case_007 date read month first |
| v2 | alternative category caps confidence; date grounding, day first | 1.000 | 0.992 | two invented police numbers; p95 84.7 s from laptop load |
| v3 | police number rule in prompt and code | 1.000 | 1.000 | all gates pass |
| Broken demo | date of loss = date sent, on purpose | 1.000 | 0.992 | gates passed, regression check caught it (exit 1) |

With 20 to 30 cases, one case moves a rate by 3 to 5 points. These results show the pipeline works on this synthetic data; they are not a claim about real claims.

## Known limits and failure modes

Seen in the holdout run:

- case_045, a 3,300-word liability letter: claimant_role came back `policyholder` instead of `third_party`. Routing was still right, because liability claims always go to a senior handler.
- case_050: the police reference `IT/60522/25` was missed (returned null). Possibly a side effect of the stricter police number rule in `extract-v3`; not tuned against, because holdout is never used for tuning.

General:

- Long documents are slow on CPU: case_029 (2,400 words) takes about 2 minutes and case_045 (3,300 words) about 3 minutes.
- Classification confidence is self-reported by the model and was overconfident on an ambiguous claim (baseline case_030). The `alternative_category` rule in code compensates for this on the cases seen so far.
- PII redaction is rule based and tuned on the dev split. It reached full recall on holdout, but names are found from context cues (labels, sign-offs, "my client, X"), so unfamiliar layouts can leak names. A production system should add a named-entity detector such as Presidio.
- Text PDFs only, no OCR. Documents are in English even though claimants are German, Italian and Austrian.
- The model is small (2.3B effective parameters) and runs at temperature 0, so outputs are close to deterministic but small prompt changes can shift single answers.
