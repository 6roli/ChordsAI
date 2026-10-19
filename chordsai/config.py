"""Settings, read once from environment variables (or a local .env file).

Secrets such as GROQ_API_KEY are never written in code. Locally they come from
.env (ignored by Git); on Render they are set as secret environment variables.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"Environment variable {name} must be an integer, got {value!r}") from error


@dataclass(frozen=True)
class Settings:
    groq_api_key: str | None
    # Optional: enables the song chord search. Without it the bot only explains and plays chords.
    tavily_api_key: str | None
    # Optional fixed model; when empty the app picks an available one (see models.py).
    model: str | None
    flask_secret_key: str
    # Abuse protection for the public demo (in memory; resets when the server restarts).
    messages_per_session_per_hour: int
    messages_per_day: int
    session_ttl_minutes: int
    max_message_length: int


def load_settings() -> Settings:
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        tavily_api_key=os.getenv("TAVILY_API_KEY") or None,
        model=os.getenv("GROQ_MODEL") or None,
        # A random key per start is fine for a demo: sessions simply restart with the server.
        flask_secret_key=os.getenv("FLASK_SECRET_KEY") or os.urandom(32).hex(),
        messages_per_session_per_hour=_int("MESSAGES_PER_SESSION_PER_HOUR", 30),
        messages_per_day=_int("MESSAGES_PER_DAY", 300),
        session_ttl_minutes=_int("SESSION_TTL_MINUTES", 60),
        max_message_length=_int("MAX_MESSAGE_LENGTH", 300),
    )


settings = load_settings()
