"""Local model through Ollama (https://docs.ollama.com/api/introduction)."""

import time
from typing import Any

import ollama

from triage.llm.base import LLMResponse


class OllamaProvider:
    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        num_ctx: int = 8192,
        temperature: float = 0.0,
        timeout_s: float = 300.0,
        client: Any = None,
    ):
        self.model = model
        self.num_ctx = num_ctx
        self.temperature = temperature
        self._client = client or ollama.Client(host=host, timeout=timeout_s)

    def generate(
        self, *, system: str, prompt: str, schema: dict[str, Any] | None = None
    ) -> LLMResponse:
        start = time.perf_counter()
        response = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            format=schema,
            options={"num_ctx": self.num_ctx, "temperature": self.temperature},
            think=False,
            stream=False,
        )
        return LLMResponse(
            content=response.message.content or "",
            prompt_tokens=response.prompt_eval_count or 0,
            output_tokens=response.eval_count or 0,
            latency_s=time.perf_counter() - start,
            model=self.model,
        )
