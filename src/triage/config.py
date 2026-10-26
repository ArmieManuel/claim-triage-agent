"""Runtime settings. Override any value with an environment variable, e.g. TRIAGE_OLLAMA_MODEL,
or put it in a local .env file (see .env.example; .env is never committed)."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRIAGE_", env_file=REPO_ROOT / ".env", extra="ignore"
    )

    llm_provider: Literal["ollama", "fake", "azure", "replay"] = "ollama"
    # Recorded model answers used when llm_provider is "replay" (CI evaluation).
    cassette_path: Path = REPO_ROOT / "evals" / "cassettes" / "ci_subset.json"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e2b"
    ollama_num_ctx: int = 8192
    temperature: float = 0.0
    request_timeout_s: float = 300.0
    routing_config: Path = REPO_ROOT / "config" / "routing.yaml"
    # API: keys allowed to call /v1 (JSON list in TRIAGE_API_KEYS); none means no access.
    api_keys: list[str] = []
    max_upload_mb: float = 10.0
    # Demo page at / with a keyless /demo route. The browser never holds an API key, so the
    # route answers only requests from this machine unless demo_local_only is turned off
    # (docker-compose does that and publishes the port on 127.0.0.1 only).
    demo_enabled: bool = True
    demo_local_only: bool = True
