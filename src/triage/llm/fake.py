"""Scripted provider for tests: no model, no network."""

import time
from collections.abc import Callable
from typing import Any

from triage.llm.base import LLMResponse

Responder = Callable[[str, str, dict[str, Any] | None], str]


class FakeProvider:
    def __init__(self, script: list[str] | Responder | None = None):
        self._script = script if script is not None else []
        self.calls: list[dict[str, Any]] = []

    def generate(
        self, *, system: str, prompt: str, schema: dict[str, Any] | None = None
    ) -> LLMResponse:
        start = time.perf_counter()
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        if callable(self._script):
            content = self._script(system, prompt, schema)
        else:
            assert self._script, "FakeProvider script ran out of responses"
            content = self._script.pop(0)
        return LLMResponse(
            content=content,
            prompt_tokens=len(system.split()) + len(prompt.split()),
            output_tokens=len(content.split()),
            latency_s=time.perf_counter() - start,
            model="fake",
        )
