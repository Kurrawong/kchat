"""ADK API application with the bundled lightweight chat UI."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from litellm import model_cost

from sparql_agent.config import Settings
from sparql_agent.rate_limit import QuestionRateLimiter

PACKAGE_DIR = Path(__file__).resolve().parent
AGENTS_DIR = os.getenv("AGENTS_DIR", str(PACKAGE_DIR.parent))

RUN_PATHS = {"/run", "/run_sse"}


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

    if active.rate_limit_questions:
        limiter = QuestionRateLimiter(active.rate_limit_questions, active.rate_limit_window_seconds)

        @application.middleware("http")
        async def limit_questions(request: Request, call_next):  # type: ignore[no-untyped-def]
            if request.method == "POST" and request.url.path in RUN_PATHS:
                try:
                    payload = await request.json()
                except Exception:
                    payload = {}
                user = str(payload.get("userId") or "")
                if not user and request.client:
                    user = request.client.host
                retry_after = limiter.check(user)
                if retry_after is not None:
                    return JSONResponse(
                        {
                            "detail": (
                                f"Question limit reached ({active.rate_limit_questions} per "
                                f"{int(active.rate_limit_window_seconds)} seconds). Please try again later."
                            )
                        },
                        status_code=429,
                        # kchat allows all origins; repeat that here because this
                        # middleware runs outside the app's CORS middleware.
                        headers={"Retry-After": str(int(retry_after) + 1), "Access-Control-Allow-Origin": "*"},
                    )
            return await call_next(request)

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
