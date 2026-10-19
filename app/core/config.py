from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRETS: frozenset[str] = frozenset(
    {
        "replace-me",
        "replace_me",
        "change-me",
        "change_me",
        "changeme",
    }
)

PRODUCTION_ENVIRONMENTS: frozenset[str] = frozenset({"production", "prod"})


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    Environment variables take precedence over values supplied by
    the .env file.
    """

    app_name: str = "SandHeal"
    environment: str = "development"
    debug: bool = False

    github_webhook_secret: SecretStr = SecretStr("")
    database_url: str = "sqlite+aiosqlite:///./sandheal.db"

    auto_migrate: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        """
        Return True when the application is running in a production environment.
        """

        return self.environment.strip().lower() in PRODUCTION_ENVIRONMENTS

    @property
    def webhook_secret_configured(self) -> bool:
        """
        Return True when a usable GitHub webhook secret is configured.

        An empty secret, or a well-known placeholder such as the
        `replace-me` value shipped in `.env.example`, is treated as
        "not configured". Both values are publicly known, so accepting
        webhooks signed with them would allow forged deliveries.
        """

        secret = self.github_webhook_secret.get_secret_value().strip()

        if not secret:
            return False

        return secret.lower() not in PLACEHOLDER_SECRETS


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached application settings instance.

    Caching ensures configuration is loaded once per process.
    """
    return Settings()
