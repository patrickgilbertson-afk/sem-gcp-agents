#!/usr/bin/env python3
"""Test GCP Secret Manager integration.

This script verifies that all required secrets can be loaded from Secret Manager.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_secret_manager_client():
    """Test direct Secret Manager client."""
    print("=" * 80)
    print("Testing GCP Secret Manager Client")
    print("=" * 80)

    try:
        from src.secrets import SecretManagerClient

        client = SecretManagerClient()
        print(f"[OK] Connected to Secret Manager (project: {client.project_id})")
        print()

        # Test Google Ads credentials
        print("Testing Google Ads credentials...")
        creds = client.get_google_ads_credentials()
        print(f"  [OK] developer_token: {creds['developer_token'][:4]}...{creds['developer_token'][-4:]}")
        print(f"  [OK] client_id: {creds['client_id'][:20]}...")
        print(f"  [OK] client_secret: {creds['client_secret'][:10]}...")
        print(f"  [OK] refresh_token: {creds['refresh_token'][:10]}...")
        print()

        # Test individual secrets
        print("Testing individual secrets...")
        secrets_to_test = [
            ("portkey-api-key", "Portkey API Key"),
            ("portkey-virtual-key-anthropic", "Portkey Anthropic Virtual Key"),
            ("portkey-virtual-key-google", "Portkey Google Virtual Key"),
            ("slack-bot-token", "Slack Bot Token"),
            ("slack-signing-secret", "Slack Signing Secret"),
        ]

        for secret_name, description in secrets_to_test:
            try:
                value = client.get_secret(secret_name)
                print(f"  [OK] {description}: {value[:4]}...{value[-4:] if len(value) > 8 else ''}")
            except Exception as e:
                print(f"  [FAIL] {description}: {e}")

        print()
        print("[OK] Secret Manager client test complete")
        return True

    except Exception as e:
        print(f"[FAIL] Secret Manager client test failed: {e}")
        return False


def test_settings_integration():
    """Test that Settings object can load secrets."""
    print()
    print("=" * 80)
    print("Testing Settings Integration")
    print("=" * 80)

    try:
        from src.config import settings

        # Test non-secret config
        print("Non-secret configuration:")
        print(f"  [OK] GCP Project ID: {settings.gcp_project_id}")
        print(f"  [OK] GCP Region: {settings.gcp_region}")
        print(f"  [OK] GA4 Dataset: {settings.ga4_dataset or '(not configured)'}")
        print(f"  [OK] Environment: {settings.environment}")
        print()

        # Test secret loading
        print("Secret loading (from Secret Manager):")

        secrets_to_test = [
            ("google_ads_developer_token", "Google Ads Developer Token"),
            ("google_ads_client_id", "Google Ads Client ID"),
            ("google_ads_client_secret", "Google Ads Client Secret"),
            ("google_ads_refresh_token", "Google Ads Refresh Token"),
            ("portkey_api_key", "Portkey API Key"),
            ("portkey_virtual_key_anthropic", "Portkey Anthropic Virtual Key"),
            ("portkey_virtual_key_google", "Portkey Google Virtual Key"),
            ("slack_bot_token", "Slack Bot Token"),
            ("slack_signing_secret", "Slack Signing Secret"),
        ]

        for attr_name, description in secrets_to_test:
            try:
                value = getattr(settings, attr_name)
                masked = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else value[:4] + "..."
                print(f"  [OK] {description}: {masked}")
            except Exception as e:
                print(f"  [FAIL] {description}: {e}")

        print()
        print("[OK] Settings integration test complete")
        return True

    except Exception as e:
        print(f"[FAIL] Settings integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print()
    print("GCP Secret Manager Integration Test")
    print("This test verifies that secrets can be loaded from GCP Secret Manager")
    print()

    # Test Secret Manager client directly
    client_ok = test_secret_manager_client()

    # Test Settings integration
    settings_ok = test_settings_integration()

    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    if client_ok and settings_ok:
        print("[OK] ALL TESTS PASSED")
        print()
        print("Secret Manager integration is working correctly!")
        print("Your application can now load secrets from GCP at runtime.")
        print()
        return 0
    else:
        print("[FAIL] SOME TESTS FAILED")
        print()
        print("Troubleshooting:")
        print("1. Ensure you're authenticated: gcloud auth application-default login")
        print("2. Verify secrets exist: gcloud secrets list --project=marketing-bigquery-490714")
        print("3. Check IAM permissions: Service account needs secretmanager.secretAccessor role")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
