"""Central configuration management using Pydantic settings."""

import os
from functools import cached_property
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Secrets are loaded from GCP Secret Manager at runtime, not from .env file.
    """

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

    # Google Analytics 4 (optional)
    ga4_dataset: str = ""  # e.g., "analytics_123456789"
    ga4_property_id: str = ""  # GA4 property ID

    # Google Ads API - IDs only (secrets loaded from Secret Manager)
    google_ads_customer_id: str
    google_ads_login_customer_id: str

    # Portkey Settings (secrets loaded from Secret Manager)
    portkey_enable_cache: bool = True
    portkey_cache_ttl: int = 3600

    # Slack - Channel ID only (secrets loaded from Secret Manager)
    slack_approval_channel_id: str
    slack_approval_user_whitelist: str = ""  # Comma-separated Slack user IDs (empty = allow all)

    # =========================================================================
    # Secrets - Loaded from GCP Secret Manager
    # =========================================================================
    # These properties load secrets from GCP Secret Manager at runtime.
    # DO NOT set these in .env file - they are ignored.
    # =========================================================================

    @cached_property
    def google_ads_developer_token(self) -> str:
        """Load Google Ads developer token from Secret Manager."""
        return self._load_secret_with_fallback(
            "GOOGLE_ADS_DEVELOPER_TOKEN",
            lambda sm: sm.get_google_ads_credentials()["developer_token"],
        )

    @cached_property
    def google_ads_client_id(self) -> str:
        """Load Google Ads client ID from Secret Manager."""
        return self._load_secret_with_fallback(
            "GOOGLE_ADS_CLIENT_ID",
            lambda sm: sm.get_google_ads_credentials()["client_id"],
        )

    @cached_property
    def google_ads_client_secret(self) -> str:
        """Load Google Ads client secret from Secret Manager."""
        return self._load_secret_with_fallback(
            "GOOGLE_ADS_CLIENT_SECRET",
            lambda sm: sm.get_google_ads_credentials()["client_secret"],
        )

    @cached_property
    def google_ads_refresh_token(self) -> str:
        """Load Google Ads refresh token from Secret Manager."""
        return self._load_secret_with_fallback(
            "GOOGLE_ADS_REFRESH_TOKEN",
            lambda sm: sm.get_google_ads_credentials()["refresh_token"],
        )

    @cached_property
    def portkey_api_key(self) -> str:
        """Load Portkey API key from Secret Manager."""
        return self._load_secret_with_fallback(
            "PORTKEY_API_KEY",
            lambda sm: sm.get_secret("portkey-api-key"),
        )

    @cached_property
    def portkey_virtual_key_anthropic(self) -> str:
        """Load Portkey Anthropic virtual key from Secret Manager."""
        return self._load_secret_with_fallback(
            "PORTKEY_VIRTUAL_KEY_ANTHROPIC",
            lambda sm: sm.get_secret("portkey-virtual-key-anthropic"),
        )

    @cached_property
    def portkey_virtual_key_google(self) -> str:
        """Load Portkey Google virtual key from Secret Manager."""
        return self._load_secret_with_fallback(
            "PORTKEY_VIRTUAL_KEY_GOOGLE",
            lambda sm: sm.get_secret("portkey-virtual-key-google"),
        )

    @cached_property
    def slack_bot_token(self) -> str:
        """Load Slack bot token from Secret Manager."""
        return self._load_secret_with_fallback(
            "SLACK_BOT_TOKEN",
            lambda sm: sm.get_secret("slack-bot-token"),
        )

    @cached_property
    def slack_signing_secret(self) -> str:
        """Load Slack signing secret from Secret Manager."""
        return self._load_secret_with_fallback(
            "SLACK_SIGNING_SECRET",
            lambda sm: sm.get_secret("slack-signing-secret"),
        )

    @cached_property
    def anthropic_api_key(self) -> str | None:
        """Load Anthropic API key from Secret Manager (optional fallback)."""
        try:
            return self._load_secret_with_fallback(
                "ANTHROPIC_API_KEY",
                lambda sm: sm.get_secret("anthropic-api-key"),
            )
        except Exception:
            return None

    @cached_property
    def google_ai_api_key(self) -> str | None:
        """Load Google AI API key from Secret Manager (optional fallback)."""
        try:
            return self._load_secret_with_fallback(
                "GOOGLE_AI_API_KEY",
                lambda sm: sm.get_secret("google-ai-api-key"),
            )
        except Exception:
            return None

    @cached_property
    def api_auth_key(self) -> str | None:
        """Load API authentication key from Secret Manager (optional).

        Used for authenticating manual API calls to protected endpoints.
        If not set, only OIDC tokens (Cloud Scheduler) can access protected endpoints.
        """
        try:
            return self._load_secret_with_fallback(
                "API_AUTH_KEY",
                lambda sm: sm.get_secret("api-auth-key"),
            )
        except Exception:
            return None

    def _load_secret_with_fallback(self, env_var: str, secret_loader) -> str:
        """Load secret from Secret Manager with env var fallback.

        Args:
            env_var: Environment variable name (fallback for local dev)
            secret_loader: Function that takes SecretManagerClient and returns secret

        Returns:
            Secret value

        Raises:
            ValueError: If secret cannot be loaded from either source
        """
        # First check if env var is set (for local development without Secret Manager)
        env_value = os.getenv(env_var)
        if env_value:
            return env_value

        # Otherwise load from Secret Manager
        try:
            from src.secrets import SecretManagerClient

            # Pass the project_id from settings to avoid circular dependency
            sm = SecretManagerClient(project_id=self.gcp_project_id)
            return secret_loader(sm)
        except Exception as e:
            raise ValueError(
                f"Failed to load {env_var} from Secret Manager and not set in environment. "
                f"Error: {e}"
            )

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
