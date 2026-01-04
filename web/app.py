#!/usr/bin/env python3
"""
MCP Gateway Web UI

A modern web interface for managing Docker MCP Gateway with OCI Vault secrets integration.
Provides a local MCP marketplace and secrets hub for non-Docker Desktop environments.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import yaml

# Add parent directory to path to import oci_vault_resolver
sys.path.insert(0, str(Path(__file__).parent.parent))
from oci_vault_resolver import VaultResolver, DEFAULT_CACHE_DIR, DEFAULT_TTL

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.urandom(24)
app.config['CACHE_DIR'] = DEFAULT_CACHE_DIR
app.config['CACHE_TTL'] = DEFAULT_TTL

# MCP Catalog - curated list of popular MCP servers
MCP_CATALOG = [
    {
        "id": "filesystem",
        "name": "Filesystem",
        "description": "Read and write files on the local filesystem",
        "category": "Core",
        "install_type": "docker",
        "image": "modelcontextprotocol/filesystem:latest",
        "config_template": {
            "allowed_paths": ["/workspace"]
        }
    },
    {
        "id": "github",
        "name": "GitHub",
        "description": "Access GitHub repositories, issues, and pull requests",
        "category": "Development",
        "install_type": "docker",
        "image": "modelcontextprotocol/github:latest",
        "requires_secrets": ["GITHUB_TOKEN"],
        "config_template": {
            "GITHUB_TOKEN": "oci-vault://YOUR_COMPARTMENT_ID/github-token"
        }
    },
    {
        "id": "postgres",
        "name": "PostgreSQL",
        "description": "Query PostgreSQL databases",
        "category": "Database",
        "install_type": "docker",
        "image": "modelcontextprotocol/postgres:latest",
        "requires_secrets": ["DB_PASSWORD"],
        "config_template": {
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_USER": "postgres",
            "DB_PASSWORD": "oci-vault://YOUR_COMPARTMENT_ID/db-password",
            "DB_NAME": "postgres"
        }
    },
    {
        "id": "prometheus",
        "name": "Prometheus",
        "description": "Query Prometheus metrics",
        "category": "Monitoring",
        "install_type": "docker",
        "image": "modelcontextprotocol/prometheus:latest",
        "requires_secrets": ["PROMETHEUS_TOKEN"],
        "config_template": {
            "PROMETHEUS_URL": "http://localhost:9090",
            "PROMETHEUS_TOKEN": "oci-vault://YOUR_COMPARTMENT_ID/prometheus-token"
        }
    },
    {
        "id": "slack",
        "name": "Slack",
        "description": "Send messages and interact with Slack",
        "category": "Communication",
        "install_type": "docker",
        "image": "modelcontextprotocol/slack:latest",
        "requires_secrets": ["SLACK_TOKEN"],
        "config_template": {
            "SLACK_TOKEN": "oci-vault://YOUR_COMPARTMENT_ID/slack-token"
        }
    },
    {
        "id": "puppeteer",
        "name": "Puppeteer",
        "description": "Web browser automation",
        "category": "Automation",
        "install_type": "docker",
        "image": "modelcontextprotocol/puppeteer:latest",
        "config_template": {}
    }
]


def run_command(cmd: List[str], capture_output=True) -> Dict[str, Any]:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=30
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out after 30 seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.route('/')
def index():
    """Render the main dashboard."""
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get the status of the MCP gateway and OCI Vault connection."""
    # Check Docker MCP
    docker_status = run_command(['docker', 'mcp', '--version'])
    
    # Check OCI CLI
    oci_status = run_command(['oci', '--version'])
    
    # Check if cache directory exists
    cache_exists = Path(app.config['CACHE_DIR']).exists()
    
    # Count cached secrets
    cache_count = 0
    if cache_exists:
        cache_count = len(list(Path(app.config['CACHE_DIR']).glob('*.json')))
    
    return jsonify({
        "docker_mcp": {
            "available": docker_status["success"],
            "version": docker_status.get("stdout", "").strip() if docker_status["success"] else None,
            "error": docker_status.get("error") or docker_status.get("stderr")
        },
        "oci_vault": {
            "available": oci_status["success"],
            "version": oci_status.get("stdout", "").strip() if oci_status["success"] else None,
            "error": oci_status.get("error") or oci_status.get("stderr")
        },
        "cache": {
            "enabled": True,
            "directory": str(app.config['CACHE_DIR']),
            "ttl": app.config['CACHE_TTL'],
            "secret_count": cache_count
        }
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get the current MCP configuration."""
    result = run_command(['docker', 'mcp', 'config', 'read'])
    
    if not result["success"]:
        return jsonify({
            "error": "Failed to read MCP configuration",
            "details": result.get("error") or result.get("stderr")
        }), 500
    
    try:
        config = yaml.safe_load(result["stdout"])
        return jsonify(config)
    except yaml.YAMLError as e:
        return jsonify({
            "error": "Failed to parse MCP configuration",
            "details": str(e)
        }), 500


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update the MCP configuration."""
    try:
        config = request.get_json()
        
        # Convert to YAML
        config_yaml = yaml.dump(config, default_flow_style=False, sort_keys=False)
        
        # Write to docker mcp
        result = subprocess.run(
            ['docker', 'mcp', 'config', 'write'],
            input=config_yaml,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return jsonify({
                "error": "Failed to write MCP configuration",
                "details": result.stderr
            }), 500
        
        return jsonify({
            "success": True,
            "message": "Configuration updated successfully"
        })
        
    except Exception as e:
        return jsonify({
            "error": "Failed to update configuration",
            "details": str(e)
        }), 500


@app.route('/api/config/resolve', methods=['POST'])
def resolve_config():
    """Resolve OCI Vault references in the configuration."""
    try:
        config = request.get_json()
        
        # Get options
        ttl = request.args.get('ttl', type=int, default=DEFAULT_TTL)
        verbose = request.args.get('verbose', type=bool, default=False)
        
        # Initialize resolver
        resolver = VaultResolver(
            cache_dir=Path(app.config['CACHE_DIR']),
            ttl=ttl,
            verbose=verbose
        )
        
        # Resolve secrets
        resolved_config = resolver.resolve_config(config)
        
        return jsonify({
            "success": True,
            "config": resolved_config
        })
        
    except Exception as e:
        return jsonify({
            "error": "Failed to resolve secrets",
            "details": str(e)
        }), 500


@app.route('/api/catalog', methods=['GET'])
def get_catalog():
    """Get the MCP server catalog."""
    category = request.args.get('category')
    
    catalog = MCP_CATALOG
    if category:
        catalog = [item for item in catalog if item.get('category') == category]
    
    return jsonify({
        "servers": catalog,
        "categories": list(set(item['category'] for item in MCP_CATALOG))
    })


@app.route('/api/catalog/<server_id>', methods=['GET'])
def get_catalog_item(server_id):
    """Get details for a specific catalog item."""
    for item in MCP_CATALOG:
        if item['id'] == server_id:
            return jsonify(item)
    
    return jsonify({"error": "Server not found"}), 404


@app.route('/api/servers', methods=['GET'])
def list_servers():
    """List currently configured MCP servers."""
    result = run_command(['docker', 'mcp', 'config', 'read'])
    
    if not result["success"]:
        return jsonify({
            "error": "Failed to read MCP configuration",
            "details": result.get("error") or result.get("stderr")
        }), 500
    
    try:
        config = yaml.safe_load(result["stdout"])
        servers = config.get('servers', {})
        
        # Enrich with catalog info
        server_list = []
        for name, server_config in servers.items():
            server_info = {
                "name": name,
                "config": server_config
            }
            
            # Try to match with catalog
            for catalog_item in MCP_CATALOG:
                if catalog_item['id'] == name or catalog_item['name'].lower() == name.lower():
                    server_info.update({
                        "catalog_id": catalog_item['id'],
                        "description": catalog_item['description'],
                        "category": catalog_item['category']
                    })
                    break
            
            server_list.append(server_info)
        
        return jsonify({"servers": server_list})
        
    except Exception as e:
        return jsonify({
            "error": "Failed to parse server list",
            "details": str(e)
        }), 500


@app.route('/api/secrets', methods=['GET'])
def list_secrets():
    """List cached secrets."""
    cache_dir = Path(app.config['CACHE_DIR'])
    
    if not cache_dir.exists():
        return jsonify({"secrets": []})
    
    secrets = []
    for cache_file in cache_dir.glob('*.json'):
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
                secrets.append({
                    "cache_key": cache_data.get('cache_key', 'unknown'),
                    "cached_at": cache_data.get('cached_at', 0),
                    "age_seconds": int(time.time() - cache_data.get('cached_at', 0))
                })
        except Exception:
            continue
    
    return jsonify({"secrets": secrets})


@app.route('/api/secrets/clear', methods=['POST'])
def clear_secrets_cache():
    """Clear the secrets cache."""
    cache_dir = Path(app.config['CACHE_DIR'])
    
    if not cache_dir.exists():
        return jsonify({
            "success": True,
            "message": "Cache directory does not exist"
        })
    
    try:
        import shutil
        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        return jsonify({
            "success": True,
            "message": "Cache cleared successfully"
        })
    except Exception as e:
        return jsonify({
            "error": "Failed to clear cache",
            "details": str(e)
        }), 500


@app.route('/api/gateway/restart', methods=['POST'])
def restart_gateway():
    """Restart the MCP gateway."""
    result = run_command(['docker', 'mcp', 'gateway', 'restart'])
    
    if result["success"]:
        return jsonify({
            "success": True,
            "message": "Gateway restarted successfully"
        })
    else:
        return jsonify({
            "error": "Failed to restart gateway",
            "details": result.get("error") or result.get("stderr")
        }), 500


if __name__ == '__main__':
    # Parse command-line arguments
    import argparse
    parser = argparse.ArgumentParser(description='MCP Gateway Web UI')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║         MCP Gateway Web UI with OCI Vault Integration       ║
║                                                              ║
║  Dashboard:    http://{args.host}:{args.port:<40}║
║  API Docs:     http://{args.host}:{args.port}/api/status{' ' * 25}║
║                                                              ║
║  Features:                                                   ║
║    • MCP Server Marketplace                                  ║
║    • OCI Vault Secrets Management                            ║
║    • Configuration Editor                                    ║
║    • Server Management                                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    app.run(host=args.host, port=args.port, debug=args.debug)
