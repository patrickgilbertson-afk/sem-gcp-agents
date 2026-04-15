"""Central configuration management using Pydantic settings."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # GCP Configuration
    gcp_project_id: str
    gcp_region: str = "us-central1"
    gcp_service_account_email: str

    # BigQuery
    bq_dataset_raw: str = "sem_ads_raw"
    bq_dataset_agents: str = "sem_agents"

    # Google Ads API
    google_ads_developer_token: str
    google_ads_client_id: str
    google_ads_client_secret: str
    google_ads_refresh_token: str
    google_ads_customer_id: str
    google_ads_login_customer_id: str

    # Portkey (LLM Gateway) - REQUIRED for production
    # All LLM calls route through Portkey
    portkey_api_key: str
    portkey_virtual_key_anthropic: str
    portkey_virtual_key_google: str
    portkey_enable_cache: bool = True
    portkey_cache_ttl: int = 3600

    # Direct API Keys (DEPRECATED - only for local development fallback)
    # In production, configure these in Portkey dashboard virtual keys
    # The Portkey clients above do NOT use these keys
    anthropic_api_key: str | None = None
    google_ai_api_key: str | None = None

    # Slack
    slack_bot_token: str
    slack_signing_secret: str
    slack_approval_channel_id: str

    # Application Settings
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    dry_run: bool = True
    kill_switch_enabled: bool = False

    # Safety Limits
    max_operations_per_run: int = 10000
    max_daily_spend_increase_pct: float = 15.0
    rate_limit_requests_per_second: float = 1.0

    # Approval Settings
    approval_timeout_hours: int = 8
    approval_escalation_hours: int = 4

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_dry_run(self) -> bool:
        """Check if dry run mode is enabled."""
        return self.dry_run or self.kill_switch_enabled


# Global settings instance
settings = Settings()
