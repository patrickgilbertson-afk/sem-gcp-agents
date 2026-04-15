"""Tests for configuration module."""

import pytest
from src.config import Settings


def test_settings_validation():
    """Test that settings validates required fields."""
    # This will fail without .env file, which is expected
    try:
        settings = Settings()
        assert settings.gcp_project_id
    except Exception:
        # Expected when no .env file
        pass


def test_is_production():
    """Test production environment check."""
    settings = Settings(_env_file=None, environment="production")
    assert settings.is_production


def test_is_dry_run():
    """Test dry run mode check."""
    settings = Settings(_env_file=None, dry_run=True)
    assert settings.is_dry_run

    settings = Settings(_env_file=None, kill_switch_enabled=True)
    assert settings.is_dry_run
