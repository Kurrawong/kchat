from sparql_agent.agent import DEFAULT_INSTRUCTION, system_instruction
from sparql_agent.config import Settings
from sparql_agent.rate_limit import QuestionRateLimiter


def test_extra_instructions_are_appended_after_default_instruction():
    settings = Settings(extra_instructions="Only answer questions about widgets.")
    instruction = system_instruction(settings)
    assert "Only answer questions about widgets." in instruction
    assert DEFAULT_INSTRUCTION in instruction
    assert instruction.index(DEFAULT_INSTRUCTION) < instruction.index("Only answer questions about widgets.")


def test_extra_instructions_are_ignored_when_system_prompt_replaces_default():
    settings = Settings(system_prompt="Replacement instruction.", extra_instructions="Only answer questions about widgets.")
    instruction = system_instruction(settings)
    assert instruction.startswith("Replacement instruction.")
    assert "Only answer questions about widgets." in instruction


def test_rate_limit_settings_default_to_disabled(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_QUESTIONS", raising=False)
    monkeypatch.delenv("RATE_LIMIT_WINDOW_SECONDS", raising=False)
    settings = Settings.from_env()
    assert settings.rate_limit_questions is None
    assert settings.rate_limit_window_seconds == 3600.0


def test_rate_limit_questions_env_is_parsed(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_QUESTIONS", "15")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    settings = Settings.from_env()
    assert settings.rate_limit_questions == 15
    assert settings.rate_limit_window_seconds == 60.0


def test_rate_limiter_allows_up_to_max_questions_per_window():
    now = [0.0]
    limiter = QuestionRateLimiter(3, 60, clock=lambda: now[0])
    assert limiter.check("user-1") is None
    assert limiter.check("user-1") is None
    assert limiter.check("user-1") is None
    assert limiter.check("user-1") is not None


def test_rate_limiter_counts_per_user():
    now = [0.0]
    limiter = QuestionRateLimiter(1, 60, clock=lambda: now[0])
    assert limiter.check("user-1") is None
    assert limiter.check("user-2") is None
    assert limiter.check("user-1") is not None


def test_rate_limiter_window_frees_capacity_over_time():
    now = [0.0]
    limiter = QuestionRateLimiter(2, 60, clock=lambda: now[0])
    assert limiter.check("user-1") is None
    now[0] = 30.0
    assert limiter.check("user-1") is None
    assert limiter.check("user-1") is not None
    now[0] = 60.5
    assert limiter.check("user-1") is None


def test_rate_limiter_reports_wait_time():
    now = [0.0]
    limiter = QuestionRateLimiter(1, 60, clock=lambda: now[0])
    limiter.check("user-1")
    now[0] = 10.0
    assert limiter.check("user-1") == 50.0
    assert limiter.retry_after("user-1") == 50.0
