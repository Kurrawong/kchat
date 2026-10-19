"""Environment-backed configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit


SUPPORTED_SESSION_DATABASE_SCHEMES = {
    "sqlite",
    "sqlite+aiosqlite",
    "postgresql+asyncpg",
    "mysql+aiomysql",
}


def validate_session_database_url(value: str | None) -> str | None:
    """Validate an ADK/SQLAlchemy session database connection string."""
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError as error:
        raise ValueError("SESSION_DATABASE_URL is not a valid database URL") from error
    if parsed.scheme.lower() not in SUPPORTED_SESSION_DATABASE_SCHEMES:
        supported = ", ".join(sorted(SUPPORTED_SESSION_DATABASE_SCHEMES))
        raise ValueError(f"SESSION_DATABASE_URL must use one of these schemes: {supported}")
    if parsed.scheme.lower().startswith("sqlite"):
        if not parsed.path:
            raise ValueError("SESSION_DATABASE_URL must identify a SQLite database file")
    elif not parsed.hostname or parsed.path in {"", "/"}:
        raise ValueError("SESSION_DATABASE_URL must include a database host and name")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Agent, endpoint, authentication, and response settings."""

    sparql_endpoint: str = "/demo"
    sparql_username: str | None = None
    sparql_password: str | None = None
    sparql_bearer_token: str | None = None
    timeout_seconds: float = 30.0
    max_response_bytes: int = 10 * 1024 * 1024
    preview_items: int = 20
    model: str = "mistral/mistral-small-latest"
    context_window_tokens: int | None = None
    api_key: str | None = None
    system_prompt: str | None = None
    extra_instructions: str | None = None
    session_database_url: str | None = None
    rate_limit_questions: int | None = None
    rate_limit_window_seconds: float = 3600.0

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        endpoint = os.getenv("SPARQL_ENDPOINT") or defaults.sparql_endpoint
        if not endpoint.startswith(("http://", "https://")) and not Path(endpoint).is_absolute():
            raise ValueError("SPARQL_ENDPOINT must be an http(s) URL or absolute directory path")
        return cls(
            sparql_endpoint=endpoint,
            sparql_username=os.getenv("SPARQL_USERNAME"),
            sparql_password=os.getenv("SPARQL_PASSWORD"),
            sparql_bearer_token=os.getenv("SPARQL_BEARER_TOKEN"),
            timeout_seconds=float(os.getenv("SPARQL_TIMEOUT_SECONDS", defaults.timeout_seconds)),
            max_response_bytes=int(os.getenv("SPARQL_MAX_RESPONSE_BYTES", defaults.max_response_bytes)),
            preview_items=int(os.getenv("SPARQL_PREVIEW_ITEMS", defaults.preview_items)),
            model=os.getenv("LLM_MODEL", defaults.model),
            context_window_tokens=int(value) if (value := os.getenv("LLM_CONTEXT_WINDOW_TOKENS")) else None,
            api_key=os.getenv("LLM_API_KEY"),
            system_prompt=os.getenv("SYSTEM_PROMPT"),
            extra_instructions=os.getenv("AGENT_EXTRA_INSTRUCTIONS") or None,
            session_database_url=validate_session_database_url(os.getenv("SESSION_DATABASE_URL")),
            rate_limit_questions=int(value) if (value := os.getenv("RATE_LIMIT_QUESTIONS")) and int(value) > 0 else None,
            rate_limit_window_seconds=float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", defaults.rate_limit_window_seconds)),
        )

    @property
    def is_local(self) -> bool:
        return Path(self.sparql_endpoint).is_absolute()
