from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Network Operations Platform"
    app_env: str = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+psycopg://nop:nop_password@localhost:5432/nop"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    netbox_url: str = Field(default="")
    netbox_token: str = Field(default="")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings instance."""

    return Settings()
