"""GCP Secret Manager integration for loading secrets at runtime."""

import json
import os
from functools import lru_cache
from typing import Any

from google.cloud import secretmanager


class SecretManagerClient:
    """Client for loading secrets from GCP Secret Manager."""

    def __init__(self, project_id: str | None = None):
        """Initialize Secret Manager client.

        Args:
            project_id: GCP project ID. If None, uses GCP_PROJECT_ID env var.
        """
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID must be set")

        self.client = secretmanager.SecretManagerServiceClient()

    @lru_cache(maxsize=128)
    def get_secret(self, secret_name: str, version: str = "latest") -> str:
        """Get secret value from Secret Manager.

        Args:
            secret_name: Name of the secret (not full path)
            version: Version to access (default: "latest")

        Returns:
            Secret value as string

        Raises:
            google.api_core.exceptions.NotFound: If secret doesn't exist
        """
        name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
        response = self.client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")

    def get_google_ads_credentials(self) -> dict[str, str]:
        """Get Google Ads API credentials.

        Returns dict with keys: developer_token, client_id, client_secret, refresh_token

        First tries to load from consolidated google-ads-credentials JSON secret.
        Falls back to individual secrets if not found.
        """
        try:
            # Option A: Consolidated JSON secret
            creds_json = self.get_secret("google-ads-credentials")
            creds = json.loads(creds_json)
            return {
                "developer_token": creds["developer_token"],
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "refresh_token": creds["refresh_token"],
            }
        except Exception:
            # Option B: Individual secrets
            return {
                "developer_token": self.get_secret("google-ads-developer-token"),
                "client_id": self.get_secret("google-ads-client-id"),
                "client_secret": self.get_secret("google-ads-client-secret"),
                "refresh_token": self.get_secret("google-ads-refresh-token"),
            }


@lru_cache(maxsize=1)
def get_secret_manager_client() -> SecretManagerClient:
    """Get singleton Secret Manager client."""
    return SecretManagerClient()


def load_secret(secret_name: str) -> str:
    """Load a secret from GCP Secret Manager.

    This is the main function to use for loading secrets.
    It's cached, so repeated calls are fast.

    Args:
        secret_name: Name of the secret in Secret Manager

    Returns:
        Secret value as string
    """
    client = get_secret_manager_client()
    return client.get_secret(secret_name)
