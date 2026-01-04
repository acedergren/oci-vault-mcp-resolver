# Quick Start - MCP Gateway Web UI

Get started with the web interface in 5 minutes!

## Prerequisites

- Python 3.8+
- OCI CLI configured (optional, for OCI Vault integration)
- Docker with MCP Gateway (optional, for full functionality)

## Installation

### Step 1: Clone and Navigate

```bash
git clone <repo-url>
cd oci-vault-mcp-resolver
```

### Step 2: Install Dependencies

```bash
pip3 install --user -r requirements.txt
```

### Step 3: Start the Web UI

```bash
cd web
./start.sh
```

You should see:

```
╔══════════════════════════════════════════════════════════════╗
║         MCP Gateway Web UI with OCI Vault Integration       ║
║  Dashboard:    http://127.0.0.1:5000                        ║
╚══════════════════════════════════════════════════════════════╝
```

### Step 4: Open Your Browser

Navigate to: **http://127.0.0.1:5000**

## First Steps

### 1. Check System Status

The dashboard shows:
- ✅ **Docker MCP**: Connection status
- ✅ **OCI Vault**: Authentication status
- ✅ **Secrets Cache**: Number of cached secrets
- ✅ **MCP Servers**: Currently configured servers

### 2. Browse the Marketplace

Click **Marketplace** to see available MCP servers:

- **Filesystem**: Local file access
- **GitHub**: Repository management
- **PostgreSQL**: Database queries
- **Prometheus**: Metrics monitoring
- **Slack**: Team communication
- **Puppeteer**: Browser automation

### 3. Add Your First Server

1. Click on any server card (e.g., "Filesystem")
2. Review the configuration template
3. Click "Add to Configuration"
4. Go to the **Configuration** tab
5. Update the YAML with your settings
6. Click **Save**

### 4. Add OCI Vault Secrets

In the **Configuration** editor, use OCI Vault references:

```yaml
servers:
  github:
    config:
      GITHUB_TOKEN: oci-vault://ocid1.compartment.oc1..xxx/github-token
```

Supported formats:
- `oci-vault://ocid1.vaultsecret.oc1.xxx` - Direct OCID
- `oci-vault://ocid1.compartment.oc1..xxx/secret-name` - Compartment + name (recommended)
- `oci-vault://ocid1.vault.oc1.xxx/secret-name` - Vault + name

### 5. Resolve Secrets

Click **Resolve & Save** to:
1. Fetch secrets from OCI Vault
2. Replace references with actual values
3. Save the resolved configuration

Or use the **Quick Actions** on the dashboard:
- Click **Resolve Secrets** button

### 6. Manage Secrets Cache

Go to the **Secrets** tab to:
- View all cached secrets
- Check secret age and status
- Clear cache to force refresh

## Common Tasks

### Add a New MCP Server

1. **Marketplace** → Click server card → **Add to Configuration**
2. **Configuration** → Add your secrets
3. **Resolve & Save**
4. **Dashboard** → **Restart Gateway**

### Update a Secret

1. Update the secret in OCI Vault
2. **Secrets** → **Clear All**
3. **Dashboard** → **Resolve Secrets**

### View Server Details

1. **Dashboard** → Find server in "Configured Servers"
2. Click **View** button
3. Review configuration

### Clear Cache

Two options:
- **Dashboard** → Quick Actions → **Clear Cache**
- **Secrets** → **Clear All**

## Advanced Usage

### Remote Access

Access from your local machine via SSH tunnel:

```bash
# On server
cd oci-vault-mcp-resolver/web
./start.sh --host 0.0.0.0 --port 5000

# On local machine
ssh -L 5000:localhost:5000 user@server

# Open http://localhost:5000
```

### Docker Deployment

```bash
# Build image
docker build -t mcp-web .

# Run container
docker run -d \
  -p 5000:5000 \
  -v ~/.oci:/root/.oci:ro \
  -v cache:/root/.cache/oci-vault-mcp \
  --name mcp-web \
  mcp-web
```

### Custom Configuration

```bash
# Custom host and port
./start.sh --host 0.0.0.0 --port 8080

# Enable debug mode
./start.sh --debug

# Environment variables
export MCP_WEB_HOST=0.0.0.0
export MCP_WEB_PORT=8080
./start.sh
```

## API Usage

The web UI exposes a REST API:

```bash
# Get status
curl http://localhost:5000/api/status

# List catalog
curl http://localhost:5000/api/catalog

# Get configuration
curl http://localhost:5000/api/config

# List servers
curl http://localhost:5000/api/servers

# List cached secrets
curl http://localhost:5000/api/secrets
```

## Troubleshooting

### Web UI won't start

**Issue**: Dependencies not installed
```bash
pip3 install --user -r requirements.txt
```

**Issue**: Port already in use
```bash
./start.sh --port 8080
```

### OCI Vault not working

**Issue**: OCI CLI not configured
```bash
oci setup config
```

**Issue**: Secrets not resolving
```bash
# Clear cache
rm -rf ~/.cache/oci-vault-mcp/

# Test OCI CLI
oci vault secret list --compartment-id YOUR_COMPARTMENT_ID
```

### Docker MCP errors

**Issue**: Docker MCP not found

The web UI works with or without Docker MCP. Without Docker, you can:
- Browse the marketplace
- Manage OCI Vault secrets
- Edit configurations (save to file)

### Cannot access remotely

**Issue**: Bound to localhost only
```bash
# Allow remote access (use with caution!)
./start.sh --host 0.0.0.0

# Or use SSH tunnel (recommended)
ssh -L 5000:localhost:5000 user@server
```

## Security Notes

1. **Default**: Binds to `127.0.0.1` (localhost only)
2. **Remote Access**: Use SSH tunnels or VPN
3. **Production**: Add authentication via reverse proxy
4. **OCI Credentials**: Never expose via web UI
5. **Cache**: Files secured with 0600 permissions

## Next Steps

- ✅ Read the [full documentation](README.md)
- ✅ Explore the [API reference](README.md#api-reference)
- ✅ Learn about [Docker deployment](README.md#docker-deployment)
- ✅ Check out [remote development use cases](README.md#remote-development-use-cases)

## Support

- GitHub Issues: <repo-url>/issues
- Main README: [../README.md](../README.md)
- OCI Vault Docs: https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm

---

**Happy MCP Gateway managing! 🚀**
