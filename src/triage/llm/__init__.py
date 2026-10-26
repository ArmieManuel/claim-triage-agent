"""LLM providers behind one interface, chosen by config."""

from triage.config import Settings
from triage.llm.azure_openai import AzureOpenAIProvider
from triage.llm.base import LLMProvider, LLMResponse
from triage.llm.fake import FakeProvider
from triage.llm.ollama_client import OllamaProvider

__all__ = ["FakeProvider", "LLMProvider", "LLMResponse", "OllamaProvider", "make_provider"]


def make_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        return FakeProvider()
    if settings.llm_provider == "replay":
        from triage.llm.replay import ReplayProvider

        return ReplayProvider(settings.cassette_path)
    if settings.llm_provider == "azure":
        return AzureOpenAIProvider()
    return OllamaProvider(
        model=settings.ollama_model,
        host=settings.ollama_host,
        num_ctx=settings.ollama_num_ctx,
        temperature=settings.temperature,
        timeout_s=settings.request_timeout_s,
    )
