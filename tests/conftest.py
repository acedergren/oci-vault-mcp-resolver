"""Pytest configuration and shared fixtures."""

import json
import os
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """
    Provide a temporary cache directory for tests.

    This ensures tests don't interfere with each other or with
    the user's actual cache directory.
    """
    cache_dir = tmp_path / "oci-vault-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def mock_oci_clients() -> Generator:
    """
    Mock OCI SDK clients for testing without real credentials.

    Provides mocked SecretsClient and VaultsClient with sensible
    default responses for successful operations.
    """
    # Mock within the oci_vault_resolver module context
    with patch("oci_vault_resolver.oci.config.from_file") as mock_config, patch(
        "oci_vault_resolver.SecretsClient"
    ) as mock_secrets_class, patch("oci_vault_resolver.VaultsClient") as mock_vaults_class:

        # Mock OCI config (won't actually be used since we mock the clients)
        mock_config.return_value = {}

        # Create mock client instances
        mock_secrets_instance = Mock()
        mock_vaults_instance = Mock()

        # Mock successful secret fetch
        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = "dGVzdC12YWx1ZQ=="  # "test-value"
        mock_secrets_instance.get_secret_bundle.return_value = mock_bundle

        # Mock successful secret listing
        mock_secret = Mock()
        mock_secret.id = "ocid1.vaultsecret.oc1.iad.test123"
        mock_secret.secret_name = "test-secret"
        mock_vaults_instance.list_secrets.return_value.data = [mock_secret]

        # Client classes return our mock instances
        mock_secrets_class.return_value = mock_secrets_instance
        mock_vaults_class.return_value = mock_vaults_instance

        yield mock_secrets_instance, mock_vaults_instance


@pytest.fixture
def sample_vault_urls() -> dict:
    """Provide sample vault URLs for testing different formats."""
    return {
        "secret_ocid": "oci-vault://ocid1.vaultsecret.oc1.iad.amaaaaaa",
        "compartment_name": "oci-vault://ocid1.compartment.oc1..aaa/my-secret",
        "vault_name": "oci-vault://ocid1.vault.oc1.iad.bbb/my-secret",
        "simple_name": "oci-vault://my-secret",
        "invalid": "not-a-vault-url",
        "empty": "oci-vault://",
        "malformed": "oci-vault:///invalid///path",
    }


@pytest.fixture
def sample_config() -> dict:
    """Provide sample MCP configuration with vault references."""
    return {
        "mcpServers": {
            "database": {
                "command": "mcp-server-postgres",
                "env": {
                    "POSTGRES_PASSWORD": "oci-vault://ocid1.vaultsecret.oc1.db-password",
                    "POSTGRES_HOST": "localhost",  # No vault reference
                },
            },
            "api": {
                "command": "mcp-server-api",
                "env": {
                    "API_KEY": "oci-vault://ocid1.compartment.oc1../api-key",
                    "API_ENDPOINT": "https://api.example.com",
                },
            },
        }
    }


@pytest.fixture
def cached_secret_data() -> dict:
    """Provide sample cached secret data structure."""
    import time

    return {
        "value": "cached-test-value",
        "cached_at": time.time() - 1800,  # Cached 30 minutes ago
        "cache_key": "oci-vault://test-ocid",
    }


@pytest.fixture
def mock_oci_config_file(tmp_path: Path) -> Path:
    """
    Create a mock OCI config file for testing.

    Returns the path to the temporary config file.
    """
    config_dir = tmp_path / ".oci"
    config_dir.mkdir()

    config_file = config_dir / "config"
    config_content = """[DEFAULT]
user=ocid1.user.oc1..test
fingerprint=aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99
tenancy=ocid1.tenancy.oc1..test
region=us-ashburn-1
key_file=~/.oci/key.pem
"""
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def resolver_with_mocked_oci(temp_cache_dir: Path, mock_oci_clients):
    """
    Provide a VaultResolver instance with mocked OCI clients.

    This is the most commonly used fixture for testing VaultResolver
    methods without requiring real OCI credentials.
    """
    # Import here to avoid issues with mocking before import
    from oci_vault_resolver import VaultResolver

    # Create resolver (will use mocked clients)
    resolver = VaultResolver(cache_dir=temp_cache_dir, ttl=3600, verbose=False)

    return resolver


# ============================================================================
# Integration Test Markers
# ============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: Integration tests requiring real OCI credentials"
    )
    config.addinivalue_line("markers", "slow: Tests that take a long time to run")


def pytest_collection_modifyitems(config, items):
    """
    Skip integration tests unless explicitly requested.

    Integration tests are skipped by default to allow quick unit test runs.
    Run integration tests with: pytest -m integration
    """
    if config.getoption("-m") == "integration":
        # User wants to run integration tests
        return

    skip_integration = pytest.mark.skip(reason="Integration tests require --run-integration flag")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
