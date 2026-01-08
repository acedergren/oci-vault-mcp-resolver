"""Tests for CLI argument parsing and main() function."""

import argparse
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
import yaml

from oci_vault_resolver import DEFAULT_CACHE_DIR, DEFAULT_TTL, VaultResolver, main


class TestCLI:
    """Test suite for CLI functionality."""

    def test_argument_parsing_defaults(self):
        """Test default argument values."""
        with patch("sys.argv", ["oci_vault_resolver.py"]):
            with patch("oci_vault_resolver.yaml.safe_load") as mock_load, patch(
                "oci_vault_resolver.VaultResolver"
            ) as mock_resolver_class:

                mock_load.return_value = {"test": "config"}
                mock_resolver_instance = Mock()
                mock_resolver_instance.resolve_config.return_value = {"resolved": "config"}
                mock_resolver_class.return_value = mock_resolver_instance

                # Patch stdin/stdout to avoid actual I/O
                with patch("sys.stdin", StringIO("test: config\n")), patch(
                    "sys.stdout", StringIO()
                ):
                    main()

                # Verify resolver created with defaults
                mock_resolver_class.assert_called_once_with(
                    cache_dir=DEFAULT_CACHE_DIR,
                    ttl=DEFAULT_TTL,
                    verbose=False,
                    use_instance_principals=False,
                    config_file=None,
                    config_profile="DEFAULT",
                )

    def test_argument_parsing_custom_cache_dir(self):
        """Test custom cache directory argument."""
        custom_cache = "/tmp/custom-cache"  # nosec B108 - test fixture only
        with patch("sys.argv", ["oci_vault_resolver.py", "--cache-dir", custom_cache]):
            with patch("oci_vault_resolver.yaml.safe_load") as mock_load, patch(
                "oci_vault_resolver.VaultResolver"
            ) as mock_resolver_class:

                mock_load.return_value = {"test": "config"}
                mock_resolver_instance = Mock()
                mock_resolver_instance.resolve_config.return_value = {"resolved": "config"}
                mock_resolver_class.return_value = mock_resolver_instance

                with patch("sys.stdin", StringIO("test: config\n")), patch(
                    "sys.stdout", StringIO()
                ):
                    main()

                # Verify custom cache directory used
                call_kwargs = mock_resolver_class.call_args[1]
                assert call_kwargs["cache_dir"] == Path(custom_cache)

    def test_argument_parsing_custom_ttl(self):
        """Test custom TTL argument."""
        with patch("sys.argv", ["oci_vault_resolver.py", "--ttl", "7200"]):
            with patch("oci_vault_resolver.yaml.safe_load") as mock_load, patch(
                "oci_vault_resolver.VaultResolver"
            ) as mock_resolver_class:

                mock_load.return_value = {"test": "config"}
                mock_resolver_instance = Mock()
                mock_resolver_instance.resolve_config.return_value = {"resolved": "config"}
                mock_resolver_class.return_value = mock_resolver_instance

                with patch("sys.stdin", StringIO("test: config\n")), patch(
                    "sys.stdout", StringIO()
                ):
                    main()

                # Verify custom TTL used
                call_kwargs = mock_resolver_class.call_args[1]
                assert call_kwargs["ttl"] == 7200

    def test_argument_parsing_verbose_flag(self):
        """Test verbose flag enables logging."""
        with patch("sys.argv", ["oci_vault_resolver.py", "--verbose"]):
            with patch("oci_vault_resolver.yaml.safe_load") as mock_load, patch(
                "oci_vault_resolver.VaultResolver"
            ) as mock_resolver_class:

                mock_load.return_value = {"test": "config"}
                mock_resolver_instance = Mock()
                mock_resolver_instance.resolve_config.return_value = {"resolved": "config"}
                mock_resolver_class.return_value = mock_resolver_instance

                with patch("sys.stdin", StringIO("test: config\n")), patch(
                    "sys.stdout", StringIO()
                ):
                    main()

                # Verify verbose enabled
                call_kwargs = mock_resolver_class.call_args[1]
                assert call_kwargs["verbose"] is True

    def test_argument_parsing_instance_principals(self):
        """Test instance principals flag."""
        with patch("sys.argv", ["oci_vault_resolver.py", "--instance-principals"]):
            with patch("oci_vault_resolver.yaml.safe_load") as mock_load, patch(
                "oci_vault_resolver.VaultResolver"
            ) as mock_resolver_class:

                mock_load.return_value = {"test": "config"}
                mock_resolver_instance = Mock()
                mock_resolver_instance.resolve_config.return_value = {"resolved": "config"}
                mock_resolver_class.return_value = mock_resolver_instance

                with patch("sys.stdin", StringIO("test: config\n")), patch(
                    "sys.stdout", StringIO()
                ):
                    main()

                # Verify instance principals enabled
                call_kwargs = mock_resolver_class.call_args[1]
                assert call_kwargs["use_instance_principals"] is True

    def test_file_input_output(self, tmp_path):
        """Test reading from and writing to files."""
        input_file = tmp_path / "input.yaml"
        output_file = tmp_path / "output.yaml"

        input_config = {"servers": {"db": {"env": {"PASSWORD": "oci-vault://secret"}}}}
        resolved_config = {"servers": {"db": {"env": {"PASSWORD": "resolved-value"}}}}

        input_file.write_text(yaml.dump(input_config))

        with patch(
            "sys.argv",
            [
                "oci_vault_resolver.py",
                "-i",
                str(input_file),
                "-o",
                str(output_file),
            ],
        ):
            with patch("oci_vault_resolver.VaultResolver") as mock_resolver_class:
                mock_resolver_instance = Mock()
                mock_resolver_instance.resolve_config.return_value = resolved_config
                mock_resolver_class.return_value = mock_resolver_instance

                main()

        # Verify output file created with resolved config
        assert output_file.exists()
        output_data = yaml.safe_load(output_file.read_text())
        assert output_data == resolved_config

    def test_yaml_parse_error_handling(self):
        """Test handling of invalid YAML input."""
        invalid_yaml = "invalid: yaml: content: {"

        with patch("sys.argv", ["oci_vault_resolver.py"]):
            with patch("sys.stdin", StringIO(invalid_yaml)):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

    def test_empty_yaml_input_handling(self):
        """Test handling of empty YAML input."""
        with patch("sys.argv", ["oci_vault_resolver.py"]):
            with patch("sys.stdin", StringIO("")):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

    def test_resolver_initialization_error_handling(self):
        """Test handling of resolver initialization failures."""
        with patch("sys.argv", ["oci_vault_resolver.py"]):
            with patch("oci_vault_resolver.yaml.safe_load") as mock_load, patch(
                "oci_vault_resolver.VaultResolver"
            ) as mock_resolver_class:

                mock_load.return_value = {"test": "config"}
                mock_resolver_class.side_effect = Exception("Init failed")

                with patch("sys.stdin", StringIO("test: config\n")):
                    with pytest.raises(SystemExit) as exc_info:
                        main()

                    assert exc_info.value.code == 1

    def test_yaml_dump_error_handling(self):
        """Test handling of YAML output write errors."""
        with patch("sys.argv", ["oci_vault_resolver.py"]):
            with patch("oci_vault_resolver.yaml.safe_load") as mock_load, patch(
                "oci_vault_resolver.yaml.dump"
            ) as mock_dump, patch("oci_vault_resolver.VaultResolver") as mock_resolver_class:

                mock_load.return_value = {"test": "config"}
                mock_dump.side_effect = Exception("Write failed")

                mock_resolver_instance = Mock()
                mock_resolver_instance.resolve_config.return_value = {"resolved": "config"}
                mock_resolver_class.return_value = mock_resolver_instance

                with patch("sys.stdin", StringIO("test: config\n")), patch(
                    "sys.stdout", StringIO()
                ):
                    with pytest.raises(SystemExit) as exc_info:
                        main()

                    assert exc_info.value.code == 1

    def test_custom_config_profile(self):
        """Test custom OCI config profile argument."""
        with patch("sys.argv", ["oci_vault_resolver.py", "--profile", "PRODUCTION"]):
            with patch("oci_vault_resolver.yaml.safe_load") as mock_load, patch(
                "oci_vault_resolver.VaultResolver"
            ) as mock_resolver_class:

                mock_load.return_value = {"test": "config"}
                mock_resolver_instance = Mock()
                mock_resolver_instance.resolve_config.return_value = {"resolved": "config"}
                mock_resolver_class.return_value = mock_resolver_instance

                with patch("sys.stdin", StringIO("test: config\n")), patch(
                    "sys.stdout", StringIO()
                ):
                    main()

                # Verify custom profile used
                call_kwargs = mock_resolver_class.call_args[1]
                assert call_kwargs["config_profile"] == "PRODUCTION"
