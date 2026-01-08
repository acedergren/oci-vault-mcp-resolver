#!/usr/bin/env python3
"""GitHub MCP Server Proxy with OCI Vault Integration.

This proxy server:
1. Fetches GitHub PAT from OCI Vault using our resolver
2. Sets it as an environment variable
3. Delegates all MCP requests to the actual GitHub MCP server

Usage:
    python github_mcp_proxy.py
"""

import os
import sys

from oci_vault_resolver import VaultResolver


def main() -> None:
    """Fetch GitHub token from vault and start the real GitHub MCP server."""
    # GitHub PAT secret OCID in OCI Vault
    github_token_ocid = (
        "ocid1.vaultsecret.oc1.eu-frankfurt-1."
        "amaaaaaahhxc6pya5mp5alyg7cai5563xzl6i7x5ecuzgnfhj5bqijyapwya"
    )
    vault_url = f"oci-vault://{github_token_ocid}"

    # Resolve token from OCI Vault
    try:
        resolver = VaultResolver(config_file="~/.oci/config", verbose=False)
        github_token = resolver.resolve_secret(vault_url)

        if not github_token:
            print(
                "ERROR: Failed to resolve GitHub token from OCI Vault",
                file=sys.stderr,
            )
            sys.exit(1)

        # Validate token format
        if not github_token.startswith("ghp_"):
            print(
                "WARNING: GitHub token doesn't have expected format",
                file=sys.stderr,
            )

        # Set environment variable for the GitHub MCP server
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token

        # Start the actual GitHub MCP server
        # This uses npx to run the official GitHub MCP server
        cmd = ["npx", "-y", "@modelcontextprotocol/server-github"]

        # Execute the real server, replacing this process
        os.execvp(cmd[0], cmd)

    except Exception as e:
        print(
            f"ERROR: Failed to initialize GitHub MCP proxy: {e}",
            file=sys.stderr,
        )
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
