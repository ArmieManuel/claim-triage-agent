# Model card

Status: Phase 0. Evaluation sections are filled in only from real runs saved under `reports/`.

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

Triage of synthetic, text-based English motor and property claim PDFs for a portfolio project. Not for real claims or real personal data.

## Evaluation results

Pending Phase 4.

## Known limits and failure modes

Pending Phase 4.
