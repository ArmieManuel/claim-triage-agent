"""Record real model answers once, replay them later (CI runs the evaluation without a model).

A recorded answer is keyed by a hash of (system prompt, user prompt, JSON schema). Any change to
a prompt file, the redaction or the schema changes the key, so the replay fails loudly and asks
for a new recording instead of silently scoring stale answers.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from triage.llm.base import LLMProvider, LLMResponse


class CassetteMissError(KeyError):
    pass


def cassette_key(system: str, prompt: str, schema: dict[str, Any] | None) -> str:
    payload = json.dumps([system, prompt, schema], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RecordingProvider:
    def __init__(self, inner: LLMProvider):
        self.inner = inner
        self.recorded: dict[str, dict[str, Any]] = {}

    def generate(
        self, *, system: str, prompt: str, schema: dict[str, Any] | None = None
    ) -> LLMResponse:
        response = self.inner.generate(system=system, prompt=prompt, schema=schema)
        self.recorded[cassette_key(system, prompt, schema)] = {
            "content": response.content,
            "prompt_tokens": response.prompt_tokens,
            "output_tokens": response.output_tokens,
            "latency_s": round(response.latency_s, 3),
            "model": response.model,
        }
        return response

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.recorded, indent=1, sort_keys=True, ensure_ascii=False)
        path.write_text(text + "\n", encoding="utf-8")


class ReplayProvider:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.answers: dict[str, dict[str, Any]] = json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def model(self) -> str:
        models = {a["model"] for a in self.answers.values()}
        return f"replay of {', '.join(sorted(models)) or 'nothing'}"

    def generate(
        self, *, system: str, prompt: str, schema: dict[str, Any] | None = None
    ) -> LLMResponse:
        started = time.perf_counter()
        answer = self.answers.get(cassette_key(system, prompt, schema))
        if answer is None:
            raise CassetteMissError(
                f"no recorded answer in {self.path} for this request. A prompt, the redaction or "
                "a schema changed since recording; re-record with python -m evals.run_eval "
                "--record <cassette> on the same cases"
            )
        return LLMResponse(
            content=answer["content"],
            prompt_tokens=answer["prompt_tokens"],
            output_tokens=answer["output_tokens"],
            latency_s=time.perf_counter() - started,
            model=answer["model"],
        )
