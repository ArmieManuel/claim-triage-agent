from types import SimpleNamespace

import pytest

from triage.config import Settings
from triage.llm import FakeProvider, LLMResponse, OllamaProvider, make_provider
from triage.llm.azure_openai import AzureOpenAIProvider


def test_fake_provider_returns_scripted_answers_in_order():
    fake = FakeProvider(['{"a": 1}', '{"a": 2}'])
    first = fake.generate(system="s", prompt="p1")
    second = fake.generate(system="s", prompt="p2", schema={"type": "object"})
    assert (first.content, second.content) == ('{"a": 1}', '{"a": 2}')
    assert [call["prompt"] for call in fake.calls] == ["p1", "p2"]
    assert fake.calls[1]["schema"] == {"type": "object"}


def test_fake_provider_fails_loudly_when_script_runs_out():
    fake = FakeProvider([])
    with pytest.raises(AssertionError):
        fake.generate(system="s", prompt="p")


def test_fake_provider_accepts_a_responder_function():
    fake = FakeProvider(lambda system, prompt, schema: prompt.upper())
    assert fake.generate(system="s", prompt="hi").content == "HI"


def test_fake_provider_reports_token_counts():
    response = FakeProvider(["one two three"]).generate(system="s", prompt="a b")
    assert isinstance(response, LLMResponse)
    assert response.output_tokens == 3
    assert response.prompt_tokens == 3  # system + prompt words


class StubOllamaClient:
    def __init__(self):
        self.kwargs = None

    def chat(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            message=SimpleNamespace(content='{"ok": true}'),
            prompt_eval_count=120,
            eval_count=15,
        )


def test_ollama_provider_sends_schema_options_and_no_thinking():
    client = StubOllamaClient()
    provider = OllamaProvider(model="gemma4:e2b", num_ctx=8192, temperature=0.0, client=client)
    schema = {"type": "object"}
    response = provider.generate(system="sys", prompt="doc", schema=schema)

    assert client.kwargs["model"] == "gemma4:e2b"
    assert client.kwargs["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "doc"},
    ]
    assert client.kwargs["format"] == schema
    assert client.kwargs["options"] == {"num_ctx": 8192, "temperature": 0.0}
    assert client.kwargs["think"] is False
    assert client.kwargs["stream"] is False
    assert response.content == '{"ok": true}'
    assert (response.prompt_tokens, response.output_tokens) == (120, 15)
    assert response.model == "gemma4:e2b"
    assert response.latency_s >= 0


def test_make_provider_picks_the_configured_backend():
    assert isinstance(make_provider(Settings(llm_provider="fake")), FakeProvider)
    assert isinstance(make_provider(Settings(llm_provider="ollama")), OllamaProvider)


def test_azure_provider_is_a_stub_until_phase_9():
    with pytest.raises(NotImplementedError):
        AzureOpenAIProvider().generate(system="s", prompt="p")


def test_settings_read_environment_variables(monkeypatch):
    monkeypatch.setenv("TRIAGE_OLLAMA_MODEL", "other:model")
    monkeypatch.setenv("TRIAGE_OLLAMA_NUM_CTX", "16384")
    settings = Settings()
    assert settings.ollama_model == "other:model"
    assert settings.ollama_num_ctx == 16384


def test_settings_defaults_match_the_model_card():
    settings = Settings()
    assert settings.llm_provider == "ollama"
    assert settings.ollama_model == "gemma4:e2b"
    assert settings.ollama_host == "http://localhost:11434"
