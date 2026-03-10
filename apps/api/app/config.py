"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the Exec Radar API.

    Values are loaded from environment variables (or a ``.env`` file when
    ``python-dotenv`` is installed).  See ``.env.example`` for a full list.
    """

    app_env: str = Field("development", alias="APP_ENV")
    app_debug: bool = Field(False, alias="APP_DEBUG")
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")

    database_url: str = Field(
        "postgresql+asyncpg://postgres:password@localhost:5432/exec_radar",
        alias="DATABASE_URL",
    )

    model_config = {"env_file": ".env", "populate_by_name": True}


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
