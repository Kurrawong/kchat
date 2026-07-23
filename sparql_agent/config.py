"""Environment-backed configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


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
        )

    @property
    def is_local(self) -> bool:
        return Path(self.sparql_endpoint).is_absolute()
