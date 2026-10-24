"""Placeholder for Azure OpenAI. Optional Phase 9; needs the user's approval before any cloud cost."""

from typing import Any

from triage.llm.base import LLMResponse


class AzureOpenAIProvider:
    def generate(
        self, *, system: str, prompt: str, schema: dict[str, Any] | None = None
    ) -> LLMResponse:
        raise NotImplementedError("Azure OpenAI is planned for the optional Phase 9")
