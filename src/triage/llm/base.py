"""The one interface every model call goes through (PLAN.md hard rule 4)."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMResponse:
    content: str
    prompt_tokens: int
    output_tokens: int
    latency_s: float
    model: str


class LLMProvider(Protocol):
    def generate(
        self, *, system: str, prompt: str, schema: dict[str, Any] | None = None
    ) -> LLMResponse:
        """Return the model's reply. With a JSON schema, the reply must be JSON matching it."""
        ...
