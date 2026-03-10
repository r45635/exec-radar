"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings for the Exec Radar API.

    Values are read from environment variables.  A ``.env`` file in the
    project root is loaded automatically when ``pydantic-settings`` is
    configured with ``env_file``.
    """

    app_name: str = "Exec Radar"
    debug: bool = False
    api_host: str = "0.0.0.0"  # noqa: S104
    api_port: int = 8000
    log_level: str = "info"

    # Future database settings (unused for now)
    database_url: str = "postgresql+asyncpg://localhost:5432/exec_radar"

    model_config = {"env_file": ".env", "env_prefix": "EXEC_RADAR_"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings.

    Using :func:`lru_cache` avoids re-parsing environment variables on
    every access while still deferring construction until first use.
    """
    return Settings()
