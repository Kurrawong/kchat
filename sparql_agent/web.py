"""ADK API application with the bundled lightweight chat UI."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from litellm import model_cost

from sparql_agent.config import Settings

PACKAGE_DIR = Path(__file__).resolve().parent
AGENTS_DIR = os.getenv("AGENTS_DIR", str(PACKAGE_DIR.parent))

def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API app with the configured ADK session backend."""
    active = settings or Settings.from_env()
    application = get_fast_api_app(
        agents_dir=AGENTS_DIR,
        web=False,
        use_local_storage=True,
        session_service_uri=active.session_database_url,
        allow_origins=["*"],
        reload_agents=os.getenv("ADK_RELOAD_AGENTS", "false").lower() == "true",
    )

    @application.get("/kchat-config")
    async def kchat_config() -> dict[str, int | str | None]:
        """Expose non-secret model and graph details needed by the chat UI."""
        model_info = model_cost.get(active.model, {})
        context_window = active.context_window_tokens or model_info.get("max_input_tokens") or model_info.get("max_tokens")
        return {
            "model": active.model,
            "contextWindowTokens": context_window,
            "sparqlEndpoint": active.sparql_endpoint,
            "sparqlEndpointType": "Local RDF directory" if active.is_local else "Remote SPARQL endpoint",
        }

    # Added last so all ADK API and documentation routes retain precedence.
    application.mount("/", StaticFiles(directory=PACKAGE_DIR / "ui", html=True), name="kchat-ui")
    return application


app = create_app()
