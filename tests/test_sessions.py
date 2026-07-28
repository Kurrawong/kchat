from pathlib import Path

import pytest

from sparql_agent.config import Settings, validate_session_database_url


def test_session_database_url_defaults_to_adk_local_storage(monkeypatch):
    monkeypatch.delenv("SESSION_DATABASE_URL", raising=False)

    assert Settings.from_env().session_database_url is None


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:////data/kchat-sessions.db",
        "sqlite+aiosqlite:////data/kchat-sessions.db",
        "postgresql+asyncpg://kchat:secret@database/kchat",
        "mysql+aiomysql://kchat:secret@database/kchat",
    ],
)
def test_supported_session_database_urls(url):
    assert validate_session_database_url(url) == url


@pytest.mark.parametrize(
    "url, message",
    [
        ("memory://", "must use one of these schemes"),
        ("postgresql://database/kchat", "must use one of these schemes"),
        ("sqlite://", "must identify a SQLite database file"),
        ("postgresql+asyncpg:///kchat", "must include a database host and name"),
        ("mysql+aiomysql://database", "must include a database host and name"),
    ],
)
def test_invalid_session_database_urls_are_rejected(url, message):
    with pytest.raises(ValueError, match=message):
        validate_session_database_url(url)


@pytest.mark.asyncio
async def test_database_session_service_persists_sessions(tmp_path: Path):
    from google.adk.sessions import DatabaseSessionService

    database_url = f"sqlite+aiosqlite:///{tmp_path / 'sessions.db'}"
    first_service = DatabaseSessionService(db_url=database_url)
    created = await first_service.create_session(
        app_name="sparql_agent",
        user_id="user-1",
        session_id="session-1",
        state={"topic": "books"},
    )
    assert created.state == {"topic": "books"}
    await first_service.close()

    second_service = DatabaseSessionService(db_url=database_url)
    restored = await second_service.get_session(
        app_name="sparql_agent", user_id="user-1", session_id="session-1"
    )
    await second_service.close()

    assert restored is not None
    assert restored.state == {"topic": "books"}


def test_web_app_passes_session_database_url_to_adk(monkeypatch):
    import sparql_agent.web as web

    class FakeApp:
        def get(self, _path):
            return lambda function: function

        def mount(self, *_args, **_kwargs):
            pass

    calls = []

    def fake_get_fast_api_app(**kwargs):
        calls.append(kwargs)
        return FakeApp()

    monkeypatch.setattr(web, "get_fast_api_app", fake_get_fast_api_app)
    settings = Settings(session_database_url="sqlite:////data/sessions.db")

    web.create_app(settings)
    web.create_app(Settings())

    assert calls[0]["session_service_uri"] == "sqlite:////data/sessions.db"
    assert calls[0]["use_local_storage"] is True
    assert calls[1]["session_service_uri"] is None
    assert calls[1]["use_local_storage"] is True
