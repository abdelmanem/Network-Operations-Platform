from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Network Operations Platform"
    app_env: str = "development"
    secret_provider: str | None = Field(
        default=None,
        validation_alias="SECRET_PROVIDER",
        description=(
            "Secret backend selector. Independent of credential-profile "
            "provider_reference. Defaults to environment in development/test. "
            "Required and must not be environment outside those environments."
        ),
    )
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+psycopg://nop:nop_password@localhost:5432/nop"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    cache_default_ttl_seconds: int = 300
    netbox_base_url: str = Field(default="", validation_alias="NETBOX_URL")
    netbox_token: str = Field(default="", validation_alias="NETBOX_TOKEN")
    auth_secret_key: str = Field(
        default="development-secret",
        validation_alias="AUTH_SECRET_KEY",
    )
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2_592_000
    netbox_expected_version: str = Field(
        default="", validation_alias="NETBOX_EXPECTED_VERSION"
    )
    netbox_timeout_seconds: float = 10.0
    netbox_page_size: int = 100
    netbox_retry_max_attempts: int = 4
    netbox_retry_base_delay_seconds: float = 0.5
    netbox_ca_cert: str = Field(
        default="",
        validation_alias="NETBOX_CA_CERT",
        description=(
            "Path to CA certificate file for NetBox TLS verification. If not set, "
            "uses the system default trust store."
        ),
    )

    @property
    def netbox_url(self) -> str:
        """Backward-compatible NetBox base URL alias."""

        return self.netbox_base_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings instance."""

    return Settings()
