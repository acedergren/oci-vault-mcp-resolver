"""Tests for mcp_vault_proxy.py wrapper script."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import yaml

# Import wrapper module
sys.path.insert(0, str(Path(__file__).parent.parent / "wrappers"))
import mcp_vault_proxy


class TestArgumentParsing:
    """Test suite for command-line argument parsing."""

    def test_service_argument_required(self):
        """Test that --service argument is required."""
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.stderr"):  # Suppress error output
                mcp_vault_proxy.main()

        assert exc_info.value.code != 0

    def test_service_argument_parsing(self, monkeypatch):
        """Test successful parsing of --service argument."""
        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
        ]
        monkeypatch.setattr("sys.argv", test_args)

        # Mock everything after argument parsing
        with patch.object(mcp_vault_proxy, "load_config") as mock_load, patch.object(
            mcp_vault_proxy.VaultResolver, "from_config"
        ) as mock_resolver, patch.object(
            mcp_vault_proxy, "get_service_command"
        ) as mock_cmd, patch.object(
            mcp_vault_proxy, "resolve_secrets"
        ) as mock_secrets, patch.object(
            mcp_vault_proxy, "execute_mcp_server"
        ) as mock_exec:

            mock_load.return_value = {"vault": {}}
            mock_resolver.return_value = Mock()
            mock_cmd.return_value = ["echo", "test"]
            mock_secrets.return_value = {}
            mock_exec.return_value = 0

            result = mcp_vault_proxy.main()

        assert result == 0

    def test_environment_argument_parsing(self, monkeypatch):
        """Test parsing of --env/--environment argument."""
        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "postgres",
            "--env",
            "production",
        ]
        monkeypatch.setattr("sys.argv", test_args)

        with patch.object(mcp_vault_proxy, "load_config") as mock_load, patch.object(
            mcp_vault_proxy.VaultResolver, "from_config"
        ) as mock_resolver, patch.object(
            mcp_vault_proxy, "get_service_command"
        ) as mock_cmd, patch.object(
            mcp_vault_proxy, "resolve_secrets"
        ) as mock_secrets, patch.object(
            mcp_vault_proxy, "execute_mcp_server"
        ) as mock_exec:

            mock_load.return_value = {"vault": {}, "environments": {}}
            mock_resolver.return_value = Mock()
            mock_cmd.return_value = ["echo", "test"]
            mock_secrets.return_value = {}
            mock_exec.return_value = 0

            mcp_vault_proxy.main()

            # Verify environment was passed to resolve_secrets
            mock_secrets.assert_called_once()
            call_args = mock_secrets.call_args[0]
            assert call_args[2] == "production"

    def test_config_path_argument(self, tmp_path: Path, monkeypatch):
        """Test parsing of --config argument."""
        config_file = tmp_path / "custom-config.yaml"
        config_data = {"vault": {"vault_id": "test"}}
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
            "--config",
            str(config_file),
        ]
        monkeypatch.setattr("sys.argv", test_args)

        with patch.object(
            mcp_vault_proxy.VaultResolver, "from_config"
        ) as mock_resolver, patch.object(
            mcp_vault_proxy, "get_service_command"
        ) as mock_cmd, patch.object(
            mcp_vault_proxy, "resolve_secrets"
        ) as mock_secrets, patch.object(
            mcp_vault_proxy, "execute_mcp_server"
        ) as mock_exec:

            mock_resolver.return_value = Mock()
            mock_cmd.return_value = ["echo", "test"]
            mock_secrets.return_value = {}
            mock_exec.return_value = 0

            mcp_vault_proxy.main()

            # Verify config_path was used
            mock_resolver.assert_called_once_with(config_file)

    def test_custom_command_argument(self, monkeypatch):
        """Test parsing of --command argument."""
        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "custom",
            "--command",
            "python3",
            "/path/to/server.py",
        ]
        monkeypatch.setattr("sys.argv", test_args)

        with patch.object(mcp_vault_proxy, "load_config") as mock_load, patch.object(
            mcp_vault_proxy.VaultResolver, "from_config"
        ) as mock_resolver, patch.object(
            mcp_vault_proxy, "get_service_command"
        ) as mock_cmd, patch.object(
            mcp_vault_proxy, "resolve_secrets"
        ) as mock_secrets, patch.object(
            mcp_vault_proxy, "execute_mcp_server"
        ) as mock_exec:

            mock_load.return_value = {"vault": {}}
            mock_resolver.return_value = Mock()
            mock_cmd.return_value = ["python3", "/path/to/server.py"]
            mock_secrets.return_value = {}
            mock_exec.return_value = 0

            mcp_vault_proxy.main()

            # Verify custom command was used
            mock_cmd.assert_called_once()
            call_args = mock_cmd.call_args[0]
            assert call_args[2] == ["python3", "/path/to/server.py"]

    def test_verbose_flag(self, monkeypatch):
        """Test --verbose flag enables debug logging."""
        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
            "--verbose",
        ]
        monkeypatch.setattr("sys.argv", test_args)

        with patch.object(mcp_vault_proxy, "load_config") as mock_load, patch.object(
            mcp_vault_proxy.VaultResolver, "from_config"
        ) as mock_resolver, patch.object(
            mcp_vault_proxy, "get_service_command"
        ) as mock_cmd, patch.object(
            mcp_vault_proxy, "resolve_secrets"
        ) as mock_secrets, patch.object(
            mcp_vault_proxy, "execute_mcp_server"
        ) as mock_exec, patch.object(
            mcp_vault_proxy, "setup_logging"
        ) as mock_logging:

            mock_load.return_value = {"vault": {}}
            mock_resolver.return_value = Mock()
            mock_cmd.return_value = ["echo", "test"]
            mock_secrets.return_value = {}
            mock_exec.return_value = 0
            mock_logger = Mock()
            mock_logging.return_value = mock_logger

            mcp_vault_proxy.main()

            # Verify verbose=True was passed to setup_logging
            mock_logging.assert_called_once_with(verbose=True)


class TestConfigurationLoading:
    """Test suite for configuration file loading."""

    def test_load_config_from_explicit_path(self, tmp_path: Path):
        """Test loading config from explicit path parameter."""
        config_file = tmp_path / "resolver.yaml"
        config_data = {
            "vault": {"vault_id": "ocid1.vault.oc1.test"},
            "cache": {"ttl": 3600},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        logger = mcp_vault_proxy.setup_logging()
        config = mcp_vault_proxy.load_config(config_file, logger)

        assert config["vault"]["vault_id"] == "ocid1.vault.oc1.test"
        assert config["cache"]["ttl"] == 3600

    def test_load_config_from_user_directory(self, tmp_path: Path, monkeypatch):
        """Test loading config from ~/.config/oci-vault-mcp/resolver.yaml."""
        user_config_dir = tmp_path / ".config" / "oci-vault-mcp"
        user_config_dir.mkdir(parents=True)
        config_file = user_config_dir / "resolver.yaml"

        config_data = {"vault": {"vault_id": "ocid1.vault.oc1.user"}}
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Mock Path.home()
        with patch("pathlib.Path.home", return_value=tmp_path):
            logger = mcp_vault_proxy.setup_logging()
            config = mcp_vault_proxy.load_config(None, logger)

        assert config["vault"]["vault_id"] == "ocid1.vault.oc1.user"

    def test_load_config_uses_example_fallback(self, tmp_path: Path, monkeypatch):
        """Test that config falls back to example file when none found."""
        # Create empty directory to chdir into
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # Mock Path.home() to nonexistent location
        with patch("pathlib.Path.home", return_value=tmp_path / "nonexistent"):
            monkeypatch.chdir(empty_dir)

            logger = mcp_vault_proxy.setup_logging()
            # Should not raise error, should use example config as fallback
            config = mcp_vault_proxy.load_config(None, logger)

            # Example config should have vault section
            assert "vault" in config

    def test_load_config_invalid_yaml_raises_error(self, tmp_path: Path):
        """Test that invalid YAML raises yaml.YAMLError."""
        config_file = tmp_path / "resolver.yaml"
        config_file.write_text("invalid: yaml: [unclosed")

        logger = mcp_vault_proxy.setup_logging()
        with pytest.raises(yaml.YAMLError):
            mcp_vault_proxy.load_config(config_file, logger)

    def test_load_config_empty_file_continues_search(self, tmp_path: Path, monkeypatch):
        """Test that empty config file continues search for valid config."""
        # Create empty config in higher priority location
        user_config_dir = tmp_path / ".config" / "oci-vault-mcp"
        user_config_dir.mkdir(parents=True)
        empty_config = user_config_dir / "resolver.yaml"
        empty_config.write_text("")

        # Create valid config in lower priority location
        local_config = tmp_path / "resolver.yaml"
        config_data = {"vault": {"vault_id": "ocid1.vault.oc1.local"}}
        with open(local_config, "w") as f:
            yaml.dump(config_data, f)

        with patch("pathlib.Path.home", return_value=tmp_path):
            monkeypatch.chdir(tmp_path)
            logger = mcp_vault_proxy.setup_logging()
            config = mcp_vault_proxy.load_config(None, logger)

        assert config["vault"]["vault_id"] == "ocid1.vault.oc1.local"

    def test_load_config_with_services_section(self, tmp_path: Path):
        """Test loading config with services section."""
        config_file = tmp_path / "resolver.yaml"
        config_data = {
            "vault": {"vault_id": "test"},
            "services": {"custom": {"command": ["python3", "/path/to/server.py"]}},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        logger = mcp_vault_proxy.setup_logging()
        config = mcp_vault_proxy.load_config(config_file, logger)

        assert "services" in config
        assert "custom" in config["services"]
        assert config["services"]["custom"]["command"] == ["python3", "/path/to/server.py"]


class TestServiceCommandDispatch:
    """Test suite for service command resolution."""

    def test_get_service_command_default_github(self):
        """Test getting default command for github service."""
        logger = mcp_vault_proxy.setup_logging()
        config = {"vault": {}}

        command = mcp_vault_proxy.get_service_command("github", config, None, logger)

        assert command == ["npx", "-y", "@modelcontextprotocol/server-github"]

    def test_get_service_command_default_postgres(self):
        """Test getting default command for postgres service."""
        logger = mcp_vault_proxy.setup_logging()
        config = {"vault": {}}

        command = mcp_vault_proxy.get_service_command("postgres", config, None, logger)

        assert command == ["npx", "-y", "@modelcontextprotocol/server-postgres"]

    def test_get_service_command_from_config(self):
        """Test getting command from config file overrides default."""
        logger = mcp_vault_proxy.setup_logging()
        config = {
            "vault": {},
            "services": {"github": {"command": ["/usr/local/bin/custom-github-server"]}},
        }

        command = mcp_vault_proxy.get_service_command("github", config, None, logger)

        assert command == ["/usr/local/bin/custom-github-server"]

    def test_get_service_command_custom_command_override(self):
        """Test that custom command argument overrides everything."""
        logger = mcp_vault_proxy.setup_logging()
        config = {
            "vault": {},
            "services": {"github": {"command": ["/config/command"]}},
        }
        custom_command = ["python3", "/my/custom/server.py"]

        command = mcp_vault_proxy.get_service_command("github", config, custom_command, logger)

        assert command == custom_command

    def test_get_service_command_unknown_service_raises_error(self):
        """Test that unknown service raises ValueError."""
        logger = mcp_vault_proxy.setup_logging()
        config = {"vault": {}}

        with pytest.raises(ValueError) as exc_info:
            mcp_vault_proxy.get_service_command("nonexistent", config, None, logger)

        assert "Unknown service: nonexistent" in str(exc_info.value)

    def test_get_service_command_all_default_services(self):
        """Test that all default services are available."""
        logger = mcp_vault_proxy.setup_logging()
        config = {"vault": {}}

        default_services = [
            "github",
            "postgres",
            "postgresql",
            "sqlite",
            "mysql",
            "mongodb",
            "redis",
            "filesystem",
            "docker",
            "kubernetes",
            "aws",
            "gcp",
            "azure",
        ]

        for service in default_services:
            command = mcp_vault_proxy.get_service_command(service, config, None, logger)
            assert len(command) > 0
            assert command[0] in ["npx", "python3"] or command[0].startswith("/")


class TestSecretResolution:
    """Test suite for secret resolution from OCI Vault."""

    @pytest.fixture
    def mock_resolver(self):
        """Create mock VaultResolver for testing."""
        resolver = Mock()
        resolver.default_compartment_id = "ocid1.compartment.oc1..test"
        resolver.resolve_secret = Mock(return_value="secret-value")
        return resolver

    def test_resolve_secrets_basic(self, mock_resolver):
        """Test basic secret resolution."""
        logger = mcp_vault_proxy.setup_logging()
        config = {
            "vault": {"compartment_id": "ocid1.compartment.oc1..test"},
            "secrets": {
                "GITHUB_TOKEN": "mcp-github-token",
                "API_KEY": "mcp-api-key",
            },
        }

        env_vars = mcp_vault_proxy.resolve_secrets(mock_resolver, config, None, logger)

        assert len(env_vars) == 2
        assert "GITHUB_TOKEN" in env_vars
        assert "API_KEY" in env_vars
        assert env_vars["GITHUB_TOKEN"] == "secret-value"
        assert mock_resolver.resolve_secret.call_count == 2

    def test_resolve_secrets_with_environment(self, mock_resolver):
        """Test secret resolution with environment overrides."""
        logger = mcp_vault_proxy.setup_logging()
        config = {
            "vault": {"compartment_id": "ocid1.compartment.oc1..test"},
            "secrets": {
                "GITHUB_TOKEN": "mcp-github-token",
            },
            "environments": {
                "production": {
                    "secrets": {
                        "GITHUB_TOKEN": "mcp-github-token-prod",
                        "PROD_ONLY": "mcp-prod-secret",
                    }
                }
            },
        }

        env_vars = mcp_vault_proxy.resolve_secrets(mock_resolver, config, "production", logger)

        # Should have both base and production secrets
        assert "GITHUB_TOKEN" in env_vars
        assert "PROD_ONLY" in env_vars

        # Verify production secret names were used
        calls = mock_resolver.resolve_secret.call_args_list
        vault_urls = [call[0][0] for call in calls]
        assert any("mcp-github-token-prod" in url for url in vault_urls)
        assert any("mcp-prod-secret" in url for url in vault_urls)

    def test_resolve_secrets_vault_url_format(self, mock_resolver):
        """Test that secrets are resolved with correct vault URL format."""
        logger = mcp_vault_proxy.setup_logging()
        mock_resolver.default_compartment_id = "ocid1.compartment.oc1..comp123"
        config = {
            "vault": {"compartment_id": "ocid1.compartment.oc1..comp123"},
            "secrets": {
                "TEST_SECRET": "my-secret-name",
            },
        }

        mcp_vault_proxy.resolve_secrets(mock_resolver, config, None, logger)

        mock_resolver.resolve_secret.assert_called_once_with(
            "oci-vault://ocid1.compartment.oc1..comp123/my-secret-name"
        )

    def test_resolve_secrets_failed_resolution(self, mock_resolver):
        """Test handling of failed secret resolution."""
        logger = mcp_vault_proxy.setup_logging()
        mock_resolver.resolve_secret.return_value = None  # Simulate failure

        config = {
            "vault": {"compartment_id": "ocid1.compartment.oc1..test"},
            "secrets": {
                "FAILED_SECRET": "nonexistent-secret",
            },
        }

        env_vars = mcp_vault_proxy.resolve_secrets(mock_resolver, config, None, logger)

        # Should return empty dict when secrets fail
        assert "FAILED_SECRET" not in env_vars
        assert len(env_vars) == 0

    def test_resolve_secrets_partial_failure(self, mock_resolver):
        """Test that partial secret resolution continues with successful secrets."""
        logger = mcp_vault_proxy.setup_logging()

        # Mock to return success for first secret, failure for second
        def side_effect(url):
            if "success" in url:
                return "secret-value"
            return None

        mock_resolver.resolve_secret.side_effect = side_effect

        config = {
            "vault": {"compartment_id": "ocid1.compartment.oc1..test"},
            "secrets": {
                "SUCCESS_SECRET": "success-secret",
                "FAILED_SECRET": "failed-secret",
            },
        }

        env_vars = mcp_vault_proxy.resolve_secrets(mock_resolver, config, None, logger)

        assert "SUCCESS_SECRET" in env_vars
        assert "FAILED_SECRET" not in env_vars
        assert len(env_vars) == 1

    def test_resolve_secrets_no_mappings(self, mock_resolver):
        """Test behavior when no secret mappings are configured."""
        logger = mcp_vault_proxy.setup_logging()
        config = {
            "vault": {"compartment_id": "ocid1.compartment.oc1..test"},
            # No secrets section
        }

        env_vars = mcp_vault_proxy.resolve_secrets(mock_resolver, config, None, logger)

        assert len(env_vars) == 0
        mock_resolver.resolve_secret.assert_not_called()

    def test_resolve_secrets_exception_handling(self, mock_resolver):
        """Test exception handling during secret resolution."""
        logger = mcp_vault_proxy.setup_logging()
        from oci_vault_resolver import VaultResolverError

        mock_resolver.resolve_secret.side_effect = VaultResolverError("Vault error")

        config = {
            "vault": {"compartment_id": "ocid1.compartment.oc1..test"},
            "secrets": {
                "ERROR_SECRET": "error-secret",
            },
        }

        # Should not raise, but should log error and return empty dict
        env_vars = mcp_vault_proxy.resolve_secrets(mock_resolver, config, None, logger)

        assert len(env_vars) == 0


class TestCommandExecution:
    """Test suite for MCP server command execution."""

    def test_execute_mcp_server_success(self):
        """Test successful MCP server execution."""
        logger = mcp_vault_proxy.setup_logging()
        command = ["echo", "hello"]
        env_vars = {"TEST_VAR": "test_value"}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = mcp_vault_proxy.execute_mcp_server(command, env_vars, logger)

        assert result == 0
        mock_run.assert_called_once()

        # Verify environment variables were passed
        call_kwargs = mock_run.call_args[1]
        assert "TEST_VAR" in call_kwargs["env"]
        assert call_kwargs["env"]["TEST_VAR"] == "test_value"

    def test_execute_mcp_server_with_exit_code(self):
        """Test that server exit code is properly returned."""
        logger = mcp_vault_proxy.setup_logging()
        command = ["false"]  # Command that returns exit code 1
        env_vars = {}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=42)

            result = mcp_vault_proxy.execute_mcp_server(command, env_vars, logger)

        assert result == 42

    def test_execute_mcp_server_command_not_found(self):
        """Test handling of command not found error."""
        logger = mcp_vault_proxy.setup_logging()
        command = ["nonexistent-command"]
        env_vars = {}

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = mcp_vault_proxy.execute_mcp_server(command, env_vars, logger)

        assert result == 127  # Command not found exit code

    def test_execute_mcp_server_keyboard_interrupt(self):
        """Test handling of keyboard interrupt."""
        logger = mcp_vault_proxy.setup_logging()
        command = ["sleep", "1000"]
        env_vars = {}

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            result = mcp_vault_proxy.execute_mcp_server(command, env_vars, logger)

        assert result == 130  # SIGINT exit code

    def test_execute_mcp_server_preserves_environment(self):
        """Test that existing environment variables are preserved."""
        logger = mcp_vault_proxy.setup_logging()
        command = ["env"]
        env_vars = {"NEW_VAR": "new_value"}

        with patch("subprocess.run") as mock_run, patch.dict(
            "os.environ", {"EXISTING_VAR": "existing_value"}
        ):
            mock_run.return_value = Mock(returncode=0)

            mcp_vault_proxy.execute_mcp_server(command, env_vars, logger)

            call_kwargs = mock_run.call_args[1]
            env = call_kwargs["env"]

            # Should have both existing and new variables
            assert "EXISTING_VAR" in env
            assert "NEW_VAR" in env
            assert env["EXISTING_VAR"] == "existing_value"
            assert env["NEW_VAR"] == "new_value"

    def test_execute_mcp_server_stdio_forwarding(self):
        """Test that stdin/stdout/stderr are forwarded to subprocess."""
        logger = mcp_vault_proxy.setup_logging()
        command = ["cat"]
        env_vars = {}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            mcp_vault_proxy.execute_mcp_server(command, env_vars, logger)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["stdin"] == sys.stdin
            assert call_kwargs["stdout"] == sys.stdout
            assert call_kwargs["stderr"] == sys.stderr


class TestEnvironmentSelection:
    """Test suite for environment-specific configuration."""

    def test_environment_from_cli_argument(self, monkeypatch):
        """Test environment selection via --env argument."""
        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
            "--env",
            "staging",
        ]
        monkeypatch.setattr("sys.argv", test_args)

        with patch.object(mcp_vault_proxy, "load_config") as mock_load, patch.object(
            mcp_vault_proxy.VaultResolver, "from_config"
        ) as mock_resolver, patch.object(
            mcp_vault_proxy, "get_service_command"
        ) as mock_cmd, patch.object(
            mcp_vault_proxy, "resolve_secrets"
        ) as mock_secrets, patch.object(
            mcp_vault_proxy, "execute_mcp_server"
        ) as mock_exec:

            config = {
                "vault": {},
                "environments": {"staging": {"secrets": {"TEST": "staging-secret"}}},
            }
            mock_load.return_value = config
            mock_resolver.return_value = Mock()
            mock_cmd.return_value = ["echo", "test"]
            mock_secrets.return_value = {}
            mock_exec.return_value = 0

            mcp_vault_proxy.main()

            # Verify environment was passed to resolve_secrets
            call_args = mock_secrets.call_args[0]
            assert call_args[2] == "staging"

    def test_environment_from_env_var(self, monkeypatch):
        """Test environment selection via OCI_VAULT_ENVIRONMENT env var."""
        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
        ]
        monkeypatch.setattr("sys.argv", test_args)
        monkeypatch.setenv("OCI_VAULT_ENVIRONMENT", "production")

        with patch.object(mcp_vault_proxy, "load_config") as mock_load, patch.object(
            mcp_vault_proxy.VaultResolver, "from_config"
        ) as mock_resolver, patch.object(
            mcp_vault_proxy, "get_service_command"
        ) as mock_cmd, patch.object(
            mcp_vault_proxy, "resolve_secrets"
        ) as mock_secrets, patch.object(
            mcp_vault_proxy, "execute_mcp_server"
        ) as mock_exec:

            config = {
                "vault": {},
                "environments": {"production": {"secrets": {"TEST": "prod-secret"}}},
            }
            mock_load.return_value = config
            mock_resolver.return_value = Mock()
            mock_cmd.return_value = ["echo", "test"]
            mock_secrets.return_value = {}
            mock_exec.return_value = 0

            mcp_vault_proxy.main()

            # Verify environment from env var was used
            call_args = mock_secrets.call_args[0]
            assert call_args[2] == "production"

    def test_cli_environment_overrides_env_var(self, monkeypatch):
        """Test that CLI --env argument takes priority over env var."""
        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
            "--env",
            "development",
        ]
        monkeypatch.setattr("sys.argv", test_args)
        monkeypatch.setenv("OCI_VAULT_ENVIRONMENT", "production")

        with patch.object(mcp_vault_proxy, "load_config") as mock_load, patch.object(
            mcp_vault_proxy.VaultResolver, "from_config"
        ) as mock_resolver, patch.object(
            mcp_vault_proxy, "get_service_command"
        ) as mock_cmd, patch.object(
            mcp_vault_proxy, "resolve_secrets"
        ) as mock_secrets, patch.object(
            mcp_vault_proxy, "execute_mcp_server"
        ) as mock_exec:

            config = {"vault": {}, "environments": {}}
            mock_load.return_value = config
            mock_resolver.return_value = Mock()
            mock_cmd.return_value = ["echo", "test"]
            mock_secrets.return_value = {}
            mock_exec.return_value = 0

            mcp_vault_proxy.main()

            # CLI argument should win
            call_args = mock_secrets.call_args[0]
            assert call_args[2] == "development"


class TestErrorHandling:
    """Test suite for error handling scenarios."""

    def test_config_not_found_error(self, tmp_path: Path, monkeypatch):
        """Test error when config file is not found."""
        # Create empty directory to chdir into
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
        ]
        monkeypatch.setattr("sys.argv", test_args)

        # Mock home to nonexistent location and chdir to empty dir
        # VaultResolver.from_config raises ConfigurationError which is caught as VaultResolverError
        with patch("pathlib.Path.home", return_value=tmp_path / "nonexistent"):
            monkeypatch.chdir(empty_dir)
            result = mcp_vault_proxy.main()

        assert result == 3  # VaultResolverError exit code (includes ConfigurationError)

    def test_invalid_yaml_config_error(self, tmp_path: Path, monkeypatch):
        """Test error when config file contains invalid YAML."""
        config_file = tmp_path / "resolver.yaml"
        config_file.write_text("invalid: yaml: [unclosed")

        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
            "--config",
            str(config_file),
        ]
        monkeypatch.setattr("sys.argv", test_args)

        # YAMLError is caught in main's exception handler and returns exit code 1
        result = mcp_vault_proxy.main()

        assert result == 1  # Generic error exit code

    def test_unknown_service_error(self, tmp_path: Path, monkeypatch):
        """Test error when unknown service is requested."""
        config_file = tmp_path / "resolver.yaml"
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.test",
                "compartment_id": "ocid1.compartment.oc1..test",
            },
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "nonexistent-service",
            "--config",
            str(config_file),
        ]
        monkeypatch.setattr("sys.argv", test_args)

        # Mock VaultResolver to avoid OCI client initialization
        with patch.object(mcp_vault_proxy.VaultResolver, "from_config") as mock_resolver:
            mock_resolver.return_value = Mock()
            result = mcp_vault_proxy.main()

        assert result == 2  # ValueError exit code

    def test_vault_resolver_error(self, tmp_path: Path, monkeypatch):
        """Test error when VaultResolver fails."""
        from oci_vault_resolver import VaultResolverError

        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"vault": {"vault_id": "test"}}, f)

        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
            "--config",
            str(config_file),
        ]
        monkeypatch.setattr("sys.argv", test_args)

        with patch.object(mcp_vault_proxy.VaultResolver, "from_config") as mock_resolver:
            mock_resolver.side_effect = VaultResolverError("Vault connection failed")

            result = mcp_vault_proxy.main()

        assert result == 3  # VaultResolverError exit code

    def test_keyboard_interrupt_handling(self, tmp_path: Path, monkeypatch):
        """Test graceful handling of keyboard interrupt."""
        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"vault": {}}, f)

        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
            "--config",
            str(config_file),
        ]
        monkeypatch.setattr("sys.argv", test_args)

        with patch.object(mcp_vault_proxy.VaultResolver, "from_config") as mock_resolver:
            mock_resolver.side_effect = KeyboardInterrupt()

            result = mcp_vault_proxy.main()

        assert result == 130  # SIGINT exit code

    def test_unexpected_exception_handling(self, tmp_path: Path, monkeypatch):
        """Test handling of unexpected exceptions."""
        config_file = tmp_path / "resolver.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"vault": {}}, f)

        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
            "--config",
            str(config_file),
        ]
        monkeypatch.setattr("sys.argv", test_args)

        with patch.object(mcp_vault_proxy.VaultResolver, "from_config") as mock_resolver:
            mock_resolver.side_effect = RuntimeError("Unexpected error")

            result = mcp_vault_proxy.main()

        assert result == 1  # Generic error exit code


class TestIntegrationScenarios:
    """Test suite for end-to-end integration scenarios."""

    def test_full_workflow_success(self, tmp_path: Path, monkeypatch):
        """Test complete workflow from config load to command execution."""
        # Create config file
        config_file = tmp_path / "resolver.yaml"
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.test",
                "compartment_id": "ocid1.compartment.oc1..test",
            },
            "secrets": {
                "GITHUB_TOKEN": "mcp-github-token",
            },
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "github",
            "--config",
            str(config_file),
        ]
        monkeypatch.setattr("sys.argv", test_args)

        # Mock all external dependencies
        with patch.object(
            mcp_vault_proxy.VaultResolver, "from_config"
        ) as mock_resolver_class, patch("subprocess.run") as mock_run:

            mock_resolver = Mock()
            mock_resolver.default_compartment_id = "ocid1.compartment.oc1..test"
            mock_resolver.resolve_secret.return_value = "github-token-value"
            mock_resolver_class.return_value = mock_resolver

            mock_run.return_value = Mock(returncode=0)

            result = mcp_vault_proxy.main()

        assert result == 0

        # Verify resolver was called
        mock_resolver.resolve_secret.assert_called_once()

        # Verify command was executed with secrets
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert "GITHUB_TOKEN" in call_kwargs["env"]
        assert call_kwargs["env"]["GITHUB_TOKEN"] == "github-token-value"

    def test_production_environment_workflow(self, tmp_path: Path, monkeypatch):
        """Test workflow with production environment overrides."""
        config_file = tmp_path / "resolver.yaml"
        config_data = {
            "vault": {
                "vault_id": "ocid1.vault.oc1.test",
                "compartment_id": "ocid1.compartment.oc1..dev",
            },
            "secrets": {
                "API_KEY": "mcp-api-key-dev",
            },
            "environments": {
                "production": {
                    "vault": {
                        "compartment_id": "ocid1.compartment.oc1..prod",
                    },
                    "secrets": {
                        "API_KEY": "mcp-api-key-prod",
                    },
                },
            },
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        test_args = [
            "mcp_vault_proxy.py",
            "--service",
            "postgres",
            "--env",
            "production",
            "--config",
            str(config_file),
        ]
        monkeypatch.setattr("sys.argv", test_args)

        with patch.object(
            mcp_vault_proxy.VaultResolver, "from_config"
        ) as mock_resolver_class, patch("subprocess.run") as mock_run:

            mock_resolver = Mock()
            mock_resolver.default_compartment_id = "ocid1.compartment.oc1..test"
            mock_resolver.resolve_secret.return_value = "prod-api-key"
            mock_resolver_class.return_value = mock_resolver

            mock_run.return_value = Mock(returncode=0)

            result = mcp_vault_proxy.main()

        assert result == 0

        # Verify production secret was resolved
        call_args = mock_resolver.resolve_secret.call_args[0]
        assert "mcp-api-key-prod" in call_args[0]


class TestLogging:
    """Test suite for logging functionality."""

    def test_setup_logging_verbose_mode(self):
        """Test that verbose mode sets DEBUG level."""
        logger = mcp_vault_proxy.setup_logging(verbose=True)

        assert logger.level == mcp_vault_proxy.logging.DEBUG

    def test_setup_logging_normal_mode(self):
        """Test that normal mode sets INFO level."""
        logger = mcp_vault_proxy.setup_logging(verbose=False)

        assert logger.level == mcp_vault_proxy.logging.INFO

    def test_logging_output_format(self):
        """Test that log messages have correct format."""
        logger = mcp_vault_proxy.setup_logging()

        # Check that handler has correct formatter
        handler = logger.handlers[0]
        assert handler.formatter is not None
        assert "[%(levelname)s]" in handler.formatter._fmt
