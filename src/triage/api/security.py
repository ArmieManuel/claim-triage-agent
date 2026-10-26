"""API key check for versioned routes. Keys come from settings, never from code."""

import secrets
from collections.abc import Callable

from fastapi import Security
from fastapi.security import APIKeyHeader

from triage.api.errors import ApiError
from triage.config import Settings

api_key_header = APIKeyHeader(
    name="X-API-Key", auto_error=False, description="Key from TRIAGE_API_KEYS"
)


def require_api_key(settings: Settings) -> Callable[[str | None], None]:
    def check(key: str | None = Security(api_key_header)) -> None:
        if not key:
            raise ApiError(401, "missing_api_key", "send your key in the X-API-Key header")
        # compare_digest takes the same time for any wrong key, so timing reveals nothing.
        if not any(secrets.compare_digest(key, allowed) for allowed in settings.api_keys):
            raise ApiError(401, "invalid_api_key", "the API key is not valid")

    return check
