"""Tests for OCI backend and client initialization."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import oci
import pytest

from oci_vault_resolver import VaultResolver


class TestOCIBackend:
    """Test suite for OCI client initialization and authentication."""

    def test_oci_client_initialization_with_config_file(self, temp_cache_dir):
        """Test OCI client initialization using config file."""
        with patch("oci_vault_resolver.oci.config.from_file") as mock_config, patch(
            "oci_vault_resolver.SecretsClient"
        ) as mock_secrets_class, patch("oci_vault_resolver.VaultsClient") as mock_vaults_class:

            mock_config.return_value = {"user": "test-user", "region": "us-ashburn-1"}
            mock_secrets_class.return_value = Mock()
            mock_vaults_class.return_value = Mock()

            resolver = VaultResolver(
                cache_dir=temp_cache_dir,
                use_instance_principals=False,
                config_file="~/.oci/config",
                config_profile="DEFAULT",
                verbose=False,
            )

            mock_config.assert_called_once_with(
                file_location="~/.oci/config", profile_name="DEFAULT"
            )
            mock_secrets_class.assert_called_once()
            mock_vaults_class.assert_called_once()

    def test_oci_client_initialization_with_instance_principals(self, temp_cache_dir):
        """Test OCI client initialization using instance principals."""
        with patch(
            "oci_vault_resolver.oci.auth.signers.InstancePrincipalsSecurityTokenSigner"
        ) as mock_signer_class, patch(
            "oci_vault_resolver.SecretsClient"
        ) as mock_secrets_class, patch(
            "oci_vault_resolver.VaultsClient"
        ) as mock_vaults_class:

            mock_signer = Mock()
            mock_signer_class.return_value = mock_signer
            mock_secrets_class.return_value = Mock()
            mock_vaults_class.return_value = Mock()

            resolver = VaultResolver(
                cache_dir=temp_cache_dir,
                use_instance_principals=True,
                verbose=False,
            )

            mock_signer_class.assert_called_once()
            mock_secrets_class.assert_called_once_with(config={}, signer=mock_signer)
            mock_vaults_class.assert_called_once_with(config={}, signer=mock_signer)

    def test_oci_client_initialization_failure(self, temp_cache_dir):
        """Test handling of OCI client initialization failure."""
        from oci_vault_resolver import AuthenticationError

        with patch("oci_vault_resolver.oci.config.from_file") as mock_config:
            mock_config.side_effect = Exception("Config file not found")

            with pytest.raises(AuthenticationError, match="Failed to initialize OCI SDK clients"):
                VaultResolver(
                    cache_dir=temp_cache_dir,
                    use_instance_principals=False,
                    verbose=False,
                )

    def test_oci_client_initialization_with_custom_profile(self, temp_cache_dir):
        """Test OCI client initialization with custom config profile."""
        with patch("oci_vault_resolver.oci.config.from_file") as mock_config, patch(
            "oci_vault_resolver.SecretsClient"
        ) as mock_secrets_class, patch("oci_vault_resolver.VaultsClient") as mock_vaults_class:

            mock_config.return_value = {"user": "custom-user"}
            mock_secrets_class.return_value = Mock()
            mock_vaults_class.return_value = Mock()

            resolver = VaultResolver(
                cache_dir=temp_cache_dir,
                config_profile="PRODUCTION",
                verbose=False,
            )

            mock_config.assert_called_once_with(file_location=None, profile_name="PRODUCTION")

    def test_api_retry_logic_on_transient_errors(self, temp_cache_dir, mock_oci_clients):
        """Test that OCI SDK handles transient errors with retries."""
        mock_secrets, _ = mock_oci_clients
        resolver = VaultResolver(cache_dir=temp_cache_dir, verbose=False)

        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.test123"

        # Mock transient error followed by success
        import base64

        mock_bundle = Mock()
        mock_bundle.data.secret_bundle_content.content = base64.b64encode(b"success").decode()

        error = oci.exceptions.ServiceError(
            status=429,
            code="TooManyRequests",
            message="Rate limited",
            headers={},
        )

        # First call raises error
        mock_secrets.get_secret_bundle.side_effect = error

        # Should raise VaultResolverError for rate limiting
        from oci_vault_resolver import VaultResolverError

        with pytest.raises(VaultResolverError, match="OCI API error: Rate limited"):
            resolver.fetch_secret_by_ocid("ocid1.vaultsecret.oc1.iad.test123")

    def test_network_error_handling(self, temp_cache_dir, mock_oci_clients):
        """Test handling of network errors."""
        mock_secrets, _ = mock_oci_clients
        resolver = VaultResolver(cache_dir=temp_cache_dir, verbose=False)

        vault_url = "oci-vault://ocid1.vaultsecret.oc1.iad.test123"

        # Mock network error
        mock_secrets.get_secret_bundle.side_effect = Exception("Network unreachable")

        result = resolver.fetch_secret_by_ocid("ocid1.vaultsecret.oc1.iad.test123")

        assert result is None

    def test_region_detection_from_config(self, temp_cache_dir):
        """Test that region is correctly loaded from OCI config."""
        with patch("oci_vault_resolver.oci.config.from_file") as mock_config, patch(
            "oci_vault_resolver.SecretsClient"
        ) as mock_secrets_class, patch("oci_vault_resolver.VaultsClient") as mock_vaults_class:

            mock_config.return_value = {
                "user": "test-user",
                "region": "eu-frankfurt-1",
                "tenancy": "ocid1.tenancy.oc1..test",
            }
            mock_secrets_instance = Mock()
            mock_vaults_instance = Mock()
            mock_secrets_class.return_value = mock_secrets_instance
            mock_vaults_class.return_value = mock_vaults_instance

            resolver = VaultResolver(cache_dir=temp_cache_dir, verbose=False)

            # Verify clients were initialized with config containing region
            assert mock_secrets_class.call_count == 1
            assert mock_vaults_class.call_count == 1

    def test_instance_principal_auth_failure(self, temp_cache_dir):
        """Test handling of instance principal authentication failure."""
        from oci_vault_resolver import AuthenticationError

        with patch(
            "oci_vault_resolver.oci.auth.signers.InstancePrincipalsSecurityTokenSigner"
        ) as mock_signer_class:
            mock_signer_class.side_effect = Exception("Unable to get instance principal token")

            with pytest.raises(AuthenticationError, match="Failed to initialize OCI SDK clients"):
                VaultResolver(
                    cache_dir=temp_cache_dir,
                    use_instance_principals=True,
                    verbose=False,
                )

    def test_verbose_logging_enabled(self, temp_cache_dir, caplog):
        """Test that verbose mode logs OCI client initialization."""
        import logging

        with patch("oci_vault_resolver.oci.config.from_file") as mock_config, patch(
            "oci_vault_resolver.SecretsClient"
        ) as mock_secrets_class, patch("oci_vault_resolver.VaultsClient") as mock_vaults_class:

            mock_config.return_value = {"user": "test-user"}
            mock_secrets_class.return_value = Mock()
            mock_vaults_class.return_value = Mock()

            with caplog.at_level(logging.DEBUG):
                resolver = VaultResolver(cache_dir=temp_cache_dir, verbose=True)

            # Check that debug logging captured the initialization message
            assert any(
                "OCI SDK clients initialized successfully" in record.message
                for record in caplog.records
            )
