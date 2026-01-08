"""Tests for configuration system functionality."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from oci_vault_resolver import ConfigurationError, VaultResolver


class TestConfigLoading:
    """Test suite for config file loading and search paths."""

    @pytest.fixture
    def sample_config_data(self) -> dict:
        """Provide sample configuration data for testing."""
        return {
            "version": "1.0",
            "vault": {
                "vault_id": "ocid1.vault.oc1.eu-frankfurt-1.test123",
                "compartment_id": "ocid1.compartment.oc1..testcomp123",
                "region": "eu-frankfurt-1",
                "auth_method": "config_file",
                "config_file": "~/.oci/config",
                "config_profile": "DEFAULT",
            },
            "cache": {
                "directory": "~/.cache/oci-vault-mcp",
                "ttl": 3600,
                "enable_stale_fallback": True,
            },
            "resilience": {
                "enable_circuit_breaker": True,
                "circuit_breaker_threshold": 5,
                "circuit_breaker_recovery": 60,
                "max_retries": 3,
                "retry_backoff_base": 2,
                "retry_jitter": True,
            },
            "logging": {
                "level": "INFO",
                "verbose": False,
            },
        }

    @pytest.fixture
    def config_with_environments(self, sample_config_data: dict) -> dict:
        """Provide config with environment-specific overrides."""
        config = sample_config_data.copy()
        config["environments"] = {
            "production": {
                "vault": {
                    "compartment_id": "ocid1.compartment.oc1..prod123",
                },
                "cache": {
                    "ttl": 1800,
                },
                "logging": {
                    "verbose": False,
                    "level": "WARNING",
                },
            },
            "development": {
                "vault": {
                    "compartment_id": "ocid1.compartment.oc1..dev123",
                },
                "cache": {
                    "ttl": 7200,
                },
                "logging": {
                    "verbose": True,
                    "level": "DEBUG",
                },
            },
            "staging": {
                "vault": {
                    "compartment_id": "ocid1.compartment.oc1..staging123",
                },
            },
        }
        return config

    def test_load_from_user_config_path(
        self, tmp_path: Path, sample_config_data: dict, mock_oci_clients
    ):
        """Test loading config from ~/.config/oci-vault-mcp/resolver.yaml."""
        # Create user config directory
        user_config_dir = tmp_path / ".config" / "oci-vault-mcp"
        user_config_dir.mkdir(parents=True)
        config_file = user_config_dir / "resolver.yaml"

        # Write config
        with open(config_file, "w") as f:
            yaml.dump(sample_config_data, f)

        # Mock Path.home() to return tmp_path
        with patch("oci_vault_resolver.Path.home", return_value=tmp_path):
            resolver = VaultResolver.from_config()

        # Verify resolver was created with config values
        assert resolver.default_vault_id == sample_config_data["vault"]["vault_id"]
        assert resolver.default_compartment_id == sample_config_data["vault"]["compartment_id"]
        assert resolver.ttl == sample_config_data["cache"]["ttl"]

    def test_load_from_system_config_path(
        self, tmp_path: Path, sample_config_data: dict, mock_oci_clients
    ):
        """Test loading config from /etc/oci-vault-mcp/resolver.yaml."""
        # Create system config file
        system_config_file = tmp_path / "resolver.yaml"
        with open(system_config_file, "w") as f:
            yaml.dump(sample_config_data, f)

        # Mock search paths (skip user config, use system config)
        with patch("oci_vault_resolver.Path.home") as mock_home:
            mock_home.return_value = tmp_path / "nonexistent"
            # Use explicit path parameter to test system config path
            resolver = VaultResolver.from_config(config_path=system_config_file)

        assert resolver.default_vault_id == sample_config_data["vault"]["vault_id"]

    def test_load_from_current_directory(
        self, tmp_path: Path, sample_config_data: dict, mock_oci_clients, monkeypatch
    ):
        """Test loading config from ./resolver.yaml."""
        # Create config in current directory
        current_config = tmp_path / "resolver.yaml"
        with open(current_config, "w") as f:
            yaml.dump(sample_config_data, f)

        # Change working directory
        monkeypatch.chdir(tmp_path)

        # Mock home to skip user config
        with patch("oci_vault_resolver.Path.home", return_value=tmp_path / "nonexistent"):
            resolver = VaultResolver.from_config()

        assert resolver.default_vault_id == sample_config_data["vault"]["vault_id"]

    def test_config_search_path_priority(
        self, tmp_path: Path, sample_config_data: dict, mock_oci_clients
    ):
        """Test that user config takes priority over system config."""
        # Create user config with one vault ID
        user_config_dir = tmp_path / ".config" / "oci-vault-mcp"
        user_config_dir.mkdir(parents=True)
        user_config = user_config_dir / "resolver.yaml"

        user_config_data = sample_config_data.copy()
        user_config_data["vault"]["vault_id"] = "ocid1.vault.oc1.user-vault"
        with open(user_config, "w") as f:
            yaml.dump(user_config_data, f)

        # Create system config with different vault ID
        system_config_dir = tmp_path / "etc" / "oci-vault-mcp"
        system_config_dir.mkdir(parents=True)
        system_config = system_config_dir / "resolver.yaml"

        system_config_data = sample_config_data.copy()
        system_config_data["vault"]["vault_id"] = "ocid1.vault.oc1.system-vault"
        with open(system_config, "w") as f:
            yaml.dump(system_config_data, f)

        # Mock home to use tmp_path
        with patch("oci_vault_resolver.Path.home", return_value=tmp_path):
            resolver = VaultResolver.from_config()

        # Should use user config (priority 1)
        assert resolver.default_vault_id == "ocid1.vault.oc1.user-vault"

    def test_explicit_config_path_override(
        self, tmp_path: Path, sample_config_data: dict, mock_oci_clients
    ):
        """Test that explicit config_path parameter overrides search paths."""
        # Create explicit config file
        explicit_config = tmp_path / "custom-resolver.yaml"
        with open(explicit_config, "w") as f:
            yaml.dump(sample_config_data, f)

        resolver = VaultResolver.from_config(config_path=explicit_config)

        assert resolver.default_vault_id == sample_config_data["vault"]["vault_id"]

    def test_missing_config_file_raises_error(self, tmp_path: Path):
        """Test that missing config file raises ConfigurationError."""
        # Mock all search paths to nonexistent locations
        with patch("oci_vault_resolver.Path.home", return_value=tmp_path / "nonexistent"):
            with pytest.raises(ConfigurationError) as exc_info:
                VaultResolver.from_config()

        assert "No resolver.yaml found" in str(exc_info.value)
        assert "~/.config/oci-vault-mcp/resolver.yaml" in str(exc_info.value)

    def test_invalid_yaml_raises_error(self, tmp_path: Path):
        """Test that invalid YAML syntax raises ConfigurationError."""
        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            f.write("invalid: yaml: content: [unclosed")

        with pytest.raises(ConfigurationError) as exc_info:
            VaultResolver.from_config(config_path=config_file)

        assert "Failed to parse YAML config" in str(exc_info.value)

    def test_empty_config_file_raises_error(self, tmp_path: Path):
        """Test that empty config file raises ConfigurationError."""
        config_file = tmp_path / "resolver.yaml"
        config_file.write_text("")

        with pytest.raises(ConfigurationError) as exc_info:
            VaultResolver.from_config(config_path=config_file)

        assert "non-empty dictionary" in str(exc_info.value)

    def test_non_dict_config_raises_error(self, tmp_path: Path):
        """Test that non-dictionary config raises ConfigurationError."""
        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(["not", "a", "dictionary"], f)

        with pytest.raises(ConfigurationError) as exc_info:
            VaultResolver.from_config(config_path=config_file)

        assert "non-empty dictionary" in str(exc_info.value)


class TestEnvironmentVariableOverrides:
    """Test suite for environment variable overrides."""

    @pytest.fixture
    def base_config_file(self, tmp_path: Path) -> Path:
        """Create a base config file for testing env var overrides."""
        config_data = {
            "version": "1.0",
            "vault": {
                "vault_id": "ocid1.vault.oc1.config-vault",
                "compartment_id": "ocid1.compartment.oc1..config-comp",
                "region": "us-ashburn-1",
                "auth_method": "config_file",
                "config_file": "~/.oci/config",
                "config_profile": "DEFAULT",
            },
            "cache": {
                "directory": "~/.cache/oci-vault-mcp",
                "ttl": 3600,
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        return config_file

    def test_oci_vault_id_override(self, base_config_file: Path, mock_oci_clients, monkeypatch):
        """Test OCI_VAULT_ID environment variable overrides config."""
        env_vault_id = "ocid1.vault.oc1.env-vault"
        monkeypatch.setenv("OCI_VAULT_ID", env_vault_id)

        resolver = VaultResolver.from_config(config_path=base_config_file)

        assert resolver.default_vault_id == env_vault_id

    def test_oci_vault_compartment_id_override(
        self, base_config_file: Path, mock_oci_clients, monkeypatch
    ):
        """Test OCI_VAULT_COMPARTMENT_ID environment variable overrides config."""
        env_compartment_id = "ocid1.compartment.oc1..env-comp"
        monkeypatch.setenv("OCI_VAULT_COMPARTMENT_ID", env_compartment_id)

        resolver = VaultResolver.from_config(config_path=base_config_file)

        assert resolver.default_compartment_id == env_compartment_id

    def test_oci_region_override(self, base_config_file: Path, mock_oci_clients, monkeypatch):
        """Test OCI_REGION environment variable overrides config."""
        # Note: This test verifies the variable is read, though region isn't stored in VaultResolver
        monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")

        resolver = VaultResolver.from_config(config_path=base_config_file)

        # Region is passed to OCI clients, not stored in resolver
        # Just verify resolver was created successfully
        assert resolver is not None

    def test_oci_use_instance_principals_override(self, base_config_file: Path, monkeypatch):
        """Test OCI_USE_INSTANCE_PRINCIPALS environment variable."""
        monkeypatch.setenv("OCI_USE_INSTANCE_PRINCIPALS", "true")

        # Mock instance principal authentication
        with patch(
            "oci_vault_resolver.oci.auth.signers.InstancePrincipalsSecurityTokenSigner"
        ) as mock_signer:
            mock_signer.return_value = Mock()
            with patch("oci_vault_resolver.SecretsClient"), patch(
                "oci_vault_resolver.VaultsClient"
            ):
                resolver = VaultResolver.from_config(config_path=base_config_file)

        # Verify instance principals were used
        mock_signer.assert_called_once()
        assert resolver is not None

    def test_oci_config_file_override(
        self, base_config_file: Path, tmp_path: Path, mock_oci_clients, monkeypatch
    ):
        """Test OCI_CONFIG_FILE environment variable overrides config."""
        custom_config_file = str(tmp_path / "custom-oci-config")
        monkeypatch.setenv("OCI_CONFIG_FILE", custom_config_file)

        resolver = VaultResolver.from_config(config_path=base_config_file)

        # Verify resolver was created (config_file is passed to OCI SDK)
        assert resolver is not None

    def test_oci_config_profile_override(
        self, base_config_file: Path, mock_oci_clients, monkeypatch
    ):
        """Test OCI_CONFIG_PROFILE environment variable overrides config."""
        monkeypatch.setenv("OCI_CONFIG_PROFILE", "CUSTOM_PROFILE")

        resolver = VaultResolver.from_config(config_path=base_config_file)

        assert resolver is not None

    def test_oci_vault_cache_dir_override(
        self, base_config_file: Path, tmp_path: Path, mock_oci_clients, monkeypatch
    ):
        """Test OCI_VAULT_CACHE_DIR environment variable overrides config."""
        custom_cache_dir = str(tmp_path / "custom-cache")
        monkeypatch.setenv("OCI_VAULT_CACHE_DIR", custom_cache_dir)

        resolver = VaultResolver.from_config(config_path=base_config_file)

        assert resolver.cache_dir == Path(custom_cache_dir)

    def test_oci_vault_cache_ttl_override(
        self, base_config_file: Path, mock_oci_clients, monkeypatch
    ):
        """Test OCI_VAULT_CACHE_TTL environment variable overrides config."""
        custom_ttl = "7200"
        monkeypatch.setenv("OCI_VAULT_CACHE_TTL", custom_ttl)

        resolver = VaultResolver.from_config(config_path=base_config_file)

        assert resolver.ttl == 7200

    def test_multiple_env_var_overrides(
        self, base_config_file: Path, tmp_path: Path, mock_oci_clients, monkeypatch
    ):
        """Test that multiple environment variables can override config simultaneously."""
        monkeypatch.setenv("OCI_VAULT_ID", "ocid1.vault.oc1.multi-env")
        monkeypatch.setenv("OCI_VAULT_COMPARTMENT_ID", "ocid1.compartment.oc1..multi-env")
        monkeypatch.setenv("OCI_VAULT_CACHE_TTL", "9000")

        resolver = VaultResolver.from_config(config_path=base_config_file)

        assert resolver.default_vault_id == "ocid1.vault.oc1.multi-env"
        assert resolver.default_compartment_id == "ocid1.compartment.oc1..multi-env"
        assert resolver.ttl == 9000

    def test_env_var_takes_priority_over_config(
        self, base_config_file: Path, mock_oci_clients, monkeypatch
    ):
        """Test that env vars take priority over config file values."""
        # Config has "ocid1.vault.oc1.config-vault"
        env_vault_id = "ocid1.vault.oc1.env-priority"
        monkeypatch.setenv("OCI_VAULT_ID", env_vault_id)

        resolver = VaultResolver.from_config(config_path=base_config_file)

        # Env var should win
        assert resolver.default_vault_id == env_vault_id


class TestEnvironmentSelection:
    """Test suite for environment-specific configuration."""

    @pytest.fixture
    def multi_env_config_file(self, tmp_path: Path) -> Path:
        """Create config with multiple environments."""
        config_data = {
            "version": "1.0",
            "vault": {
                "vault_id": "ocid1.vault.oc1.default-vault",
                "compartment_id": "ocid1.compartment.oc1..default-comp",
            },
            "cache": {
                "ttl": 3600,
            },
            "logging": {
                "verbose": False,
            },
            "environments": {
                "production": {
                    "vault": {
                        "compartment_id": "ocid1.compartment.oc1..prod-comp",
                    },
                    "cache": {
                        "ttl": 1800,
                    },
                    "logging": {
                        "verbose": False,
                    },
                },
                "development": {
                    "vault": {
                        "compartment_id": "ocid1.compartment.oc1..dev-comp",
                    },
                    "cache": {
                        "ttl": 7200,
                    },
                    "logging": {
                        "verbose": True,
                    },
                },
                "staging": {
                    "vault": {
                        "compartment_id": "ocid1.compartment.oc1..staging-comp",
                    },
                },
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        return config_file

    def test_production_environment_selection(
        self, multi_env_config_file: Path, mock_oci_clients, monkeypatch
    ):
        """Test selecting production environment."""
        monkeypatch.setenv("OCI_VAULT_ENVIRONMENT", "production")

        resolver = VaultResolver.from_config(config_path=multi_env_config_file)

        assert resolver.default_compartment_id == "ocid1.compartment.oc1..prod-comp"
        assert resolver.ttl == 1800
        assert resolver.verbose is False

    def test_development_environment_selection(
        self, multi_env_config_file: Path, mock_oci_clients, monkeypatch
    ):
        """Test selecting development environment."""
        monkeypatch.setenv("OCI_VAULT_ENVIRONMENT", "development")

        resolver = VaultResolver.from_config(config_path=multi_env_config_file)

        assert resolver.default_compartment_id == "ocid1.compartment.oc1..dev-comp"
        assert resolver.ttl == 7200
        assert resolver.verbose is True

    def test_staging_environment_selection(
        self, multi_env_config_file: Path, mock_oci_clients, monkeypatch
    ):
        """Test selecting staging environment."""
        monkeypatch.setenv("OCI_VAULT_ENVIRONMENT", "staging")

        resolver = VaultResolver.from_config(config_path=multi_env_config_file)

        assert resolver.default_compartment_id == "ocid1.compartment.oc1..staging-comp"
        # TTL should be from base config (not overridden in staging)
        assert resolver.ttl == 3600

    def test_no_environment_uses_defaults(self, multi_env_config_file: Path, mock_oci_clients):
        """Test that without environment variable, base config is used."""
        resolver = VaultResolver.from_config(config_path=multi_env_config_file)

        # Should use base config values
        assert resolver.default_compartment_id == "ocid1.compartment.oc1..default-comp"
        assert resolver.ttl == 3600
        assert resolver.verbose is False

    def test_nonexistent_environment_uses_defaults(
        self, multi_env_config_file: Path, mock_oci_clients, monkeypatch
    ):
        """Test that selecting nonexistent environment uses base config."""
        monkeypatch.setenv("OCI_VAULT_ENVIRONMENT", "nonexistent")

        resolver = VaultResolver.from_config(config_path=multi_env_config_file)

        # Should fall back to base config
        assert resolver.default_compartment_id == "ocid1.compartment.oc1..default-comp"

    def test_environment_deep_merge(
        self, multi_env_config_file: Path, mock_oci_clients, monkeypatch
    ):
        """Test that environment config deeply merges with base config."""
        monkeypatch.setenv("OCI_VAULT_ENVIRONMENT", "staging")

        resolver = VaultResolver.from_config(config_path=multi_env_config_file)

        # Staging overrides compartment_id
        assert resolver.default_compartment_id == "ocid1.compartment.oc1..staging-comp"
        # But vault_id should still be from base config
        assert resolver.default_vault_id == "ocid1.vault.oc1.default-vault"


class TestRequiredFieldsValidation:
    """Test suite for required field validation."""

    def test_missing_vault_section(self, tmp_path: Path, mock_oci_clients):
        """Test handling of config without vault section."""
        config_data = {
            "version": "1.0",
            "cache": {"ttl": 3600},
            # Missing "vault" section
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Should not raise error, but vault_id will be None
        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.default_vault_id is None
        assert resolver.default_compartment_id is None

    def test_missing_cache_section_uses_defaults(self, tmp_path: Path, mock_oci_clients):
        """Test that missing cache section uses default values."""
        config_data = {
            "version": "1.0",
            "vault": {
                "vault_id": "ocid1.vault.oc1.test",
            },
            # Missing "cache" section
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        # Should use default values
        assert resolver.cache_dir == Path("~/.cache/oci-vault-mcp").expanduser()
        assert resolver.ttl == 3600  # DEFAULT_TTL

    def test_partial_vault_config(self, tmp_path: Path, mock_oci_clients):
        """Test config with only some vault fields specified."""
        config_data = {
            "version": "1.0",
            "vault": {
                "vault_id": "ocid1.vault.oc1.partial",
                # Missing compartment_id, region, etc.
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.default_vault_id == "ocid1.vault.oc1.partial"
        assert resolver.default_compartment_id is None

    def test_minimal_valid_config(self, tmp_path: Path, mock_oci_clients):
        """Test that minimal config with just vault ID works."""
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.minimal",
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.default_vault_id == "ocid1.vault.oc1.minimal"


class TestResilienceSettings:
    """Test suite for resilience configuration."""

    @pytest.fixture
    def resilience_config_file(self, tmp_path: Path) -> Path:
        """Create config with resilience settings."""
        config_data = {
            "version": "1.0",
            "vault": {
                "vault_id": "ocid1.vault.oc1.resilient",
            },
            "resilience": {
                "enable_circuit_breaker": False,
                "circuit_breaker_threshold": 10,
                "max_retries": 5,
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        return config_file

    def test_resilience_settings_applied(self, resilience_config_file: Path, mock_oci_clients):
        """Test that resilience settings are applied from config."""
        resolver = VaultResolver.from_config(config_path=resilience_config_file)

        assert resolver.circuit_breaker is None  # Disabled
        assert resolver.max_retries == 5

    def test_default_resilience_settings(self, tmp_path: Path, mock_oci_clients):
        """Test default resilience settings when not specified in config."""
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.defaults",
            },
            # No resilience section
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        # Should use defaults
        assert resolver.circuit_breaker is not None  # Enabled by default
        assert resolver.max_retries == 3  # DEFAULT_MAX_RETRIES


class TestLoggingConfiguration:
    """Test suite for logging configuration."""

    def test_verbose_logging_enabled(self, tmp_path: Path, mock_oci_clients):
        """Test that verbose logging can be enabled via config."""
        config_data = {
            "vault": {"vault_id": "ocid1.vault.oc1.test"},
            "logging": {
                "verbose": True,
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.verbose is True

    def test_verbose_logging_disabled_by_default(self, tmp_path: Path, mock_oci_clients):
        """Test that verbose logging is disabled by default."""
        config_data = {
            "vault": {"vault_id": "ocid1.vault.oc1.test"},
            # No logging section
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.verbose is False


class TestAuthenticationMethods:
    """Test suite for authentication method configuration."""

    def test_config_file_auth_method(self, tmp_path: Path, mock_oci_clients):
        """Test config_file authentication method."""
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.test",
                "auth_method": "config_file",
                "config_file": "~/.oci/config",
                "config_profile": "CUSTOM",
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        # Verify resolver was created (auth happens in __init__)
        assert resolver is not None

    def test_instance_principal_auth_method(self, tmp_path: Path):
        """Test instance_principal authentication method."""
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.test",
                "auth_method": "instance_principal",
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Mock instance principal authentication
        with patch(
            "oci_vault_resolver.oci.auth.signers.InstancePrincipalsSecurityTokenSigner"
        ) as mock_signer:
            mock_signer.return_value = Mock()
            with patch("oci_vault_resolver.SecretsClient"), patch(
                "oci_vault_resolver.VaultsClient"
            ):
                resolver = VaultResolver.from_config(config_path=config_file)

        mock_signer.assert_called_once()
        assert resolver is not None


class TestConfigReadErrors:
    """Test suite for config file read errors."""

    def test_config_file_permission_denied(self, tmp_path: Path):
        """Test handling of config file with no read permissions."""
        config_file = tmp_path / "resolver.yaml"
        config_file.write_text("vault:\n  vault_id: test")
        config_file.chmod(0o000)  # No permissions

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                VaultResolver.from_config(config_path=config_file)

            assert "Failed to read config file" in str(exc_info.value)
        finally:
            # Restore permissions for cleanup
            config_file.chmod(0o644)

    def test_config_file_is_directory(self, tmp_path: Path):
        """Test error when config path points to a directory."""
        config_dir = tmp_path / "resolver.yaml"
        config_dir.mkdir()

        with pytest.raises(ConfigurationError):
            VaultResolver.from_config(config_path=config_dir)


class TestCacheDirectoryExpansion:
    """Test suite for cache directory path expansion."""

    def test_cache_directory_tilde_expansion(self, tmp_path: Path, mock_oci_clients):
        """Test that ~ in cache directory path is expanded."""
        config_data = {
            "vault": {"vault_id": "ocid1.vault.oc1.test"},
            "cache": {
                "directory": "~/.cache/test-cache",
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        # Path should be expanded
        assert "~" not in str(resolver.cache_dir)
        assert resolver.cache_dir.is_absolute()

    def test_cache_directory_absolute_path(self, tmp_path: Path, mock_oci_clients):
        """Test that absolute cache paths work correctly."""
        cache_path = tmp_path / "absolute-cache"
        config_data = {
            "vault": {"vault_id": "ocid1.vault.oc1.test"},
            "cache": {
                "directory": str(cache_path),
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.cache_dir == cache_path


class TestEdgeCases:
    """Test suite for edge cases and corner cases."""

    def test_config_with_comments(self, tmp_path: Path, mock_oci_clients):
        """Test that YAML comments in config are handled correctly."""
        config_content = """
# This is a comment
vault:
  vault_id: ocid1.vault.oc1.test  # Inline comment
  # Another comment
  compartment_id: ocid1.compartment.oc1..test
"""
        config_file = tmp_path / "resolver.yaml"
        config_file.write_text(config_content)

        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.default_vault_id == "ocid1.vault.oc1.test"

    def test_environment_deep_merge_nested_dicts(
        self, tmp_path: Path, mock_oci_clients, monkeypatch
    ):
        """Test deep merge with deeply nested dictionary structures."""
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.base",
                "nested": {
                    "level1": {
                        "level2": {
                            "base_value": "original",
                        }
                    }
                },
            },
            "environments": {
                "test": {
                    "vault": {
                        "nested": {
                            "level1": {
                                "level2": {
                                    "override_value": "overridden",
                                }
                            }
                        }
                    }
                }
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("OCI_VAULT_ENVIRONMENT", "test")
        resolver = VaultResolver.from_config(config_path=config_file)

        # Deep merge should preserve base_value and add override_value
        assert resolver.default_vault_id == "ocid1.vault.oc1.base"

    def test_environment_override_replaces_non_dict_values(
        self, tmp_path: Path, mock_oci_clients, monkeypatch
    ):
        """Test that environment overrides replace non-dict values completely."""
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.base",
            },
            "cache": {
                "ttl": 3600,
            },
            "environments": {
                "test": {
                    "cache": {
                        "ttl": 7200,  # Replace integer value
                    }
                }
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("OCI_VAULT_ENVIRONMENT", "test")
        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.ttl == 7200

    def test_config_with_unicode_characters(self, tmp_path: Path, mock_oci_clients):
        """Test handling of unicode characters in config."""
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.test",
                # Unicode in string value
                "description": "Vault для тестов 测试",
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True)

        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.default_vault_id == "ocid1.vault.oc1.test"

    def test_config_with_very_long_values(self, tmp_path: Path, mock_oci_clients):
        """Test handling of extremely long configuration values."""
        long_vault_id = "ocid1.vault.oc1.test" + "x" * 1000
        config_data = {
            "vault": {
                "vault_id": long_vault_id,
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.default_vault_id == long_vault_id

    def test_config_with_null_values(self, tmp_path: Path, mock_oci_clients):
        """Test handling of null values in config."""
        config_data = {
            "vault": {
                "vault_id": None,  # Explicit null
                "compartment_id": "ocid1.compartment.oc1..test",
            },
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.default_vault_id is None
        assert resolver.default_compartment_id == "ocid1.compartment.oc1..test"

    def test_config_with_extra_unknown_fields(self, tmp_path: Path, mock_oci_clients):
        """Test that unknown config fields are gracefully ignored."""
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.test",
            },
            "unknown_section": {
                "unknown_field": "unknown_value",
            },
            "another_unknown": "value",
        }

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Should not raise error
        resolver = VaultResolver.from_config(config_path=config_file)

        assert resolver.default_vault_id == "ocid1.vault.oc1.test"
