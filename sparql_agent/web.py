"""ADK API application with the bundled lightweight chat UI."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from litellm import model_cost

from sparql_agent.config import Settings

PACKAGE_DIR = Path(__file__).resolve().parent
AGENTS_DIR = os.getenv("AGENTS_DIR", str(PACKAGE_DIR.parent))

app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    web=False,
    use_local_storage=True,
    allow_origins=["*"],
    reload_agents=os.getenv("ADK_RELOAD_AGENTS", "false").lower() == "true",
)

@app.get("/kchat-config")
async def kchat_config() -> dict[str, int | str | None]:
    """Expose non-secret model limits needed by the chat usage display."""
    settings = Settings.from_env()
    model_info = model_cost.get(settings.model, {})
    context_window = settings.context_window_tokens or model_info.get("max_input_tokens") or model_info.get("max_tokens")
    return {"model": settings.model, "contextWindowTokens": context_window}


# Added last so all ADK API and documentation routes retain precedence.
app.mount("/", StaticFiles(directory=PACKAGE_DIR / "ui", html=True), name="kchat-ui")
