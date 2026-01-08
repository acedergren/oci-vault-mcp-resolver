#!/usr/bin/env python3
"""
Generic MCP Vault Proxy Wrapper.

Resolves secrets from OCI Vault and delegates to any MCP server.
Replaces hardcoded service-specific wrappers with a configurable approach.

Usage:
    # GitHub MCP server
    python3 mcp_vault_proxy.py --service github

    # PostgreSQL with production environment
    python3 mcp_vault_proxy.py --service postgres --env production

    # Custom command
    python3 mcp_vault_proxy.py --service custom --command "python3 my_server.py"

Docker MCP Gateway Integration:
    # ~/.docker/mcp/config.yaml
    servers:
      github-vault:
        command: python3
        args:
          - /usr/local/bin/mcp_vault_proxy.py
          - --service
          - github
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

# Add parent directory to path to import oci_vault_resolver
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from oci_vault_resolver import VaultResolver, VaultResolverError
except ImportError as e:
    print(
        "ERROR: Failed to import oci_vault_resolver module.",
        file=sys.stderr,
    )
    print(f"Import error: {e}", file=sys.stderr)
    print(
        "\nTroubleshooting steps:",
        file=sys.stderr,
    )
    print("1. Ensure oci_vault_resolver.py is in the parent directory", file=sys.stderr)
    print("2. Install required dependencies: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# Service command mappings (can be overridden by config file)
DEFAULT_SERVICE_COMMANDS: dict[str, list[str]] = {
    "github": ["npx", "-y", "@modelcontextprotocol/server-github"],
    "postgres": ["npx", "-y", "@modelcontextprotocol/server-postgres"],
    "postgresql": ["npx", "-y", "@modelcontextprotocol/server-postgres"],
    "sqlite": ["npx", "-y", "@modelcontextprotocol/server-sqlite"],
    "mysql": ["npx", "-y", "@modelcontextprotocol/server-mysql"],
    "mongodb": ["npx", "-y", "@modelcontextprotocol/server-mongodb"],
    "redis": ["npx", "-y", "@modelcontextprotocol/server-redis"],
    "filesystem": ["npx", "-y", "@modelcontextprotocol/server-filesystem"],
    "docker": ["npx", "-y", "@modelcontextprotocol/server-docker"],
    "kubernetes": ["npx", "-y", "@modelcontextprotocol/server-kubernetes"],
    "aws": ["npx", "-y", "@modelcontextprotocol/server-aws"],
    "gcp": ["npx", "-y", "@modelcontextprotocol/server-gcp"],
    "azure": ["npx", "-y", "@modelcontextprotocol/server-azure"],
}


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the wrapper."""
    logger = logging.getLogger("mcp_vault_proxy")
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger


def load_config(config_path: Optional[Path], logger: logging.Logger) -> dict[str, Any]:
    """
    Load configuration from file.

    Searches in priority order if config_path not specified:
      1. ~/.config/oci-vault-mcp/resolver.yaml (user-level)
      2. /etc/oci-vault-mcp/resolver.yaml (system-level)
      3. ./resolver.yaml (current directory)
      4. ../config/resolver.yaml.example (development fallback)

    Args:
        config_path: Optional explicit path to config file
        logger: Logger instance

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If no config file found
        yaml.YAMLError: If config is invalid YAML
    """
    search_paths = [
        config_path,
        Path.home() / ".config" / "oci-vault-mcp" / "resolver.yaml",
        Path("/etc/oci-vault-mcp/resolver.yaml"),
        Path("./resolver.yaml"),
        Path(__file__).parent.parent / "config" / "resolver.yaml.example",
    ]

    for path in search_paths:
        if path and path.exists():
            logger.debug(f"Loading config from: {path}")
            try:
                with open(path, "r") as f:
                    config = yaml.safe_load(f)
                    if not config or not isinstance(config, dict):
                        logger.warning(f"Config file {path} is empty or invalid")
                        continue
                    return dict(config)  # type: ignore[return-value]
            except yaml.YAMLError as e:
                logger.error(f"Failed to parse YAML config at {path}: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to read config file at {path}: {e}")
                raise

    # No config found
    error_msg = (
        "No resolver.yaml configuration file found.\n\n"
        "Searched in:\n"
        "  1. ~/.config/oci-vault-mcp/resolver.yaml (user-level)\n"
        "  2. /etc/oci-vault-mcp/resolver.yaml (system-level)\n"
        "  3. ./resolver.yaml (current directory)\n\n"
        "Setup instructions:\n"
        "  1. Copy the example config:\n"
        "     mkdir -p ~/.config/oci-vault-mcp\n"
        "     cp config/resolver.yaml.example ~/.config/oci-vault-mcp/resolver.yaml\n\n"
        "  2. Edit the config with your OCI Vault details:\n"
        "     vim ~/.config/oci-vault-mcp/resolver.yaml\n\n"
        "  3. Ensure you have OCI credentials configured:\n"
        "     ~/.oci/config (for config_file auth)\n"
        "     OR\n"
        "     Instance principal (for OCI VM auth)\n"
    )
    raise FileNotFoundError(error_msg)


def get_service_command(
    service: str,
    config: dict[str, Any],
    custom_command: Optional[list[str]],
    logger: logging.Logger,
) -> list[str]:
    """
    Get the command to execute for a given service.

    Priority:
      1. Custom command from --command flag
      2. Service command from config file
      3. Default service command from DEFAULT_SERVICE_COMMANDS

    Args:
        service: Service name (e.g., "github", "postgres")
        config: Configuration dictionary
        custom_command: Optional custom command from CLI
        logger: Logger instance

    Returns:
        Command as list of strings

    Raises:
        ValueError: If service not found and no custom command provided
    """
    if custom_command:
        logger.debug(f"Using custom command: {' '.join(custom_command)}")
        return custom_command

    # Check config file for service command
    services_config = config.get("services", {})
    if service in services_config:
        cmd = services_config[service].get("command")
        if cmd:
            logger.debug(f"Using command from config for service '{service}': {' '.join(cmd)}")
            return list(cmd)  # type: ignore[return-value]

    # Check default commands
    if service in DEFAULT_SERVICE_COMMANDS:
        cmd = DEFAULT_SERVICE_COMMANDS[service]
        logger.debug(f"Using default command for service '{service}': {' '.join(cmd)}")
        return list(cmd)  # type: ignore[return-value]

    # Service not found
    available_services = list(DEFAULT_SERVICE_COMMANDS.keys())
    error_msg = (
        f"Unknown service: {service}\n\n"
        f"Available services: {', '.join(available_services)}\n\n"
        "To use a custom service:\n"
        "  1. Define it in ~/.config/oci-vault-mcp/resolver.yaml:\n"
        "     services:\n"
        "       myservice:\n"
        "         command:\n"
        "           - python3\n"
        "           - /path/to/server.py\n\n"
        "  2. Or use --command flag:\n"
        f"     {sys.argv[0]} --service custom --command 'python3 /path/to/server.py'\n"
    )
    raise ValueError(error_msg)


def resolve_secrets(
    resolver: VaultResolver,
    config: dict[str, Any],
    environment: Optional[str],
    logger: logging.Logger,
) -> dict[str, str]:
    """
    Resolve all secrets from OCI Vault based on config mappings.

    Args:
        resolver: VaultResolver instance
        config: Configuration dictionary
        environment: Optional environment name (production, development, etc.)
        logger: Logger instance

    Returns:
        Dictionary of environment variable name -> secret value

    Raises:
        VaultResolverError: If secret resolution fails
    """
    # Get base secret mappings
    secret_mappings = config.get("secrets", {})

    # Apply environment-specific overrides
    if environment:
        env_config = config.get("environments", {}).get(environment, {})
        env_secrets = env_config.get("secrets", {})
        secret_mappings = {**secret_mappings, **env_secrets}
        logger.debug(f"Applied environment '{environment}' secret overrides")

    if not secret_mappings:
        logger.warning("No secret mappings found in configuration")
        return {}

    logger.info(f"Resolving {len(secret_mappings)} secrets from OCI Vault...")

    resolved_secrets: dict[str, str] = {}
    failed_secrets: list[str] = []

    for env_var, secret_name in secret_mappings.items():
        try:
            # Construct vault URL
            # Format: oci-vault://compartment-id/secret-name
            if resolver.default_compartment_id:
                vault_url = f"oci-vault://{resolver.default_compartment_id}/{secret_name}"
            else:
                # If no default compartment, assume secret_name is an OCID
                vault_url = f"oci-vault://{secret_name}"

            logger.debug(f"Resolving {env_var} from {secret_name}...")
            secret_value = resolver.resolve_secret(vault_url)

            if secret_value is None:
                logger.warning(f"Failed to resolve secret '{secret_name}' for {env_var}")
                failed_secrets.append(env_var)
            else:
                resolved_secrets[env_var] = secret_value
                logger.debug(f"✓ Resolved {env_var}")

        except VaultResolverError as e:
            logger.error(f"Error resolving {env_var}: {e}")
            failed_secrets.append(env_var)
        except Exception as e:
            logger.error(f"Unexpected error resolving {env_var}: {e}")
            failed_secrets.append(env_var)

    logger.info(f"Successfully resolved {len(resolved_secrets)}/{len(secret_mappings)} secrets")

    if failed_secrets:
        logger.warning(f"Failed to resolve secrets: {', '.join(failed_secrets)}")
        logger.warning(
            "\nTroubleshooting steps:\n"
            "1. Verify secrets exist in OCI Vault:\n"
            "   oci vault secret list --compartment-id YOUR_COMPARTMENT_ID\n\n"
            "2. Check secret naming convention matches config:\n"
            "   Expected format: mcp-{service}-{type}[-{env}]\n\n"
            "3. Verify IAM permissions:\n"
            "   allow group YourGroup to read secret-bundles in compartment YourCompartment\n\n"
            "4. Check OCI authentication:\n"
            "   - For config_file: ~/.oci/config must be valid\n"
            "   - For instance_principal: must run on OCI VM with correct IAM policy\n"
        )

    return resolved_secrets


def execute_mcp_server(
    command: list[str],
    env_vars: dict[str, str],
    logger: logging.Logger,
) -> int:
    """
    Execute the MCP server with resolved secrets as environment variables.

    Args:
        command: Command to execute as list of strings
        env_vars: Environment variables to set (secrets)
        logger: Logger instance

    Returns:
        Exit code of the MCP server process
    """
    # Merge with current environment
    env = os.environ.copy()
    env.update(env_vars)

    logger.info(f"Executing MCP server: {' '.join(command)}")
    logger.debug(f"Environment variables set: {', '.join(env_vars.keys())}")

    try:
        # Execute and forward stdin/stdout/stderr
        result = subprocess.run(
            command,
            env=env,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return result.returncode

    except FileNotFoundError:
        logger.error(f"Command not found: {command[0]}")
        logger.error(
            "\nTroubleshooting steps:\n"
            "1. Ensure the command is installed:\n"
            f"   which {command[0]}\n\n"
            "2. For npx commands, ensure Node.js is installed:\n"
            "   node --version\n"
            "   npx --version\n\n"
            "3. Check PATH environment variable:\n"
            "   echo $PATH\n"
        )
        return 127  # Command not found

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        logger.error(f"Failed to execute MCP server: {e}")
        return 1


def main() -> int:
    """Execute MCP vault proxy wrapper."""
    parser = argparse.ArgumentParser(
        description="Generic MCP Vault Proxy - Resolves secrets from OCI Vault for any MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # GitHub MCP server with default environment
  %(prog)s --service github

  # PostgreSQL with production environment
  %(prog)s --service postgres --env production

  # Custom service with explicit command
  %(prog)s --service custom --command "python3 /path/to/server.py"

  # Use custom config file
  %(prog)s --service github --config /path/to/resolver.yaml

  # Verbose logging for debugging
  %(prog)s --service github --verbose

Environment Variables:
  OCI_VAULT_ENVIRONMENT       Select environment (production, development, staging)
  OCI_VAULT_ID                Override vault.vault_id from config
  OCI_VAULT_COMPARTMENT_ID    Override vault.compartment_id from config
  OCI_REGION                  Override vault.region from config
  OCI_USE_INSTANCE_PRINCIPALS Set to "true" for instance principal auth
  OCI_CONFIG_FILE             Override vault.config_file from config
  OCI_CONFIG_PROFILE          Override vault.config_profile from config

For more information, see: https://github.com/yourusername/oci-vault-mcp-resolver
        """,
    )

    parser.add_argument(
        "--service",
        required=True,
        help="Service name (github, postgres, custom, etc.)",
    )

    parser.add_argument(
        "--env",
        "--environment",
        dest="environment",
        help="Environment name (production, development, staging)",
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to resolver.yaml config file (overrides search)",
    )

    parser.add_argument(
        "--command",
        nargs="+",
        help="Custom command to execute (overrides service defaults)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0",
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging(verbose=args.verbose)

    try:
        # Load configuration
        logger.debug("Loading configuration...")
        config = load_config(args.config, logger)

        # Create VaultResolver from config
        logger.debug("Initializing VaultResolver...")
        resolver = VaultResolver.from_config(args.config)

        # Get service command
        logger.debug(f"Looking up command for service: {args.service}")
        command = get_service_command(args.service, config, args.command, logger)

        # Resolve secrets from vault
        env_vars = resolve_secrets(
            resolver,
            config,
            args.environment or os.environ.get("OCI_VAULT_ENVIRONMENT"),
            logger,
        )

        # Execute MCP server
        return execute_mcp_server(command, env_vars, logger)

    except FileNotFoundError as e:
        logger.error(str(e))
        return 2

    except ValueError as e:
        logger.error(str(e))
        return 2

    except VaultResolverError as e:
        logger.error(f"Vault resolver error: {e}")
        logger.error(
            "\nTroubleshooting steps:\n"
            "1. Verify OCI authentication is configured:\n"
            "   oci session authenticate\n\n"
            "2. Test vault connectivity:\n"
            "   oci vault secret list --compartment-id YOUR_COMPARTMENT_ID\n\n"
            "3. Check IAM permissions:\n"
            "   - Read permissions on secrets\n"
            "   - Access to specified compartment\n"
        )
        return 3

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        return 130

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        logger.error(
            "\nIf this issue persists, please report it at:\n"
            "https://github.com/yourusername/oci-vault-mcp-resolver/issues"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
