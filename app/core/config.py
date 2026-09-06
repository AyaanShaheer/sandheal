from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    Environment variables take precedence over values supplied by
    the .env file.
    """

    app_name: str = "SandHeal"
    environment: str = "development"
    debug: bool = False

    github_webhook_secret: str = ""
    database_url: str = "sqlite+aiosqlite:///./sandheal.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached application settings instance.

    Caching ensures configuration is loaded once per process.
    """
    return Settings()
