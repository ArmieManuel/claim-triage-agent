"""Runtime settings. Override any value with an environment variable, e.g. TRIAGE_OLLAMA_MODEL."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRIAGE_")

    llm_provider: Literal["ollama", "fake", "azure"] = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e2b"
    ollama_num_ctx: int = 8192
    temperature: float = 0.0
    request_timeout_s: float = 300.0
    routing_config: Path = REPO_ROOT / "config" / "routing.yaml"
