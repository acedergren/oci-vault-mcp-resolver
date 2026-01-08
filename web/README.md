# MCP Gateway Web UI

A modern, powerful web interface for managing Docker MCP Gateway with OCI Vault secrets integration. Designed for non-Docker Desktop environments like servers and remote development setups.

## Features

### 🎨 Modern Dashboard
- Real-time status monitoring of Docker MCP and OCI Vault
- Visual cards showing system health and statistics
- Quick access to all major functions

### 🏪 MCP Marketplace
- Browse curated catalog of popular MCP servers
- Filter by category (Core, Development, Database, Monitoring, etc.)
- One-click installation with automatic configuration

### 🔐 Secrets Management Hub
- Manage OCI Vault secrets integration
- View cached secrets with age and status
- Clear cache and force secret refresh
- Support for multiple OCI Vault URL formats

### ⚙️ Configuration Editor
- Live YAML configuration editor
- One-click secret resolution
- Save and apply configurations directly
- Syntax highlighting and validation

### 🚀 Server Management
- List all configured MCP servers
- View server details and configuration
- Restart gateway with one click
- Add/remove servers easily

## Installation

### Prerequisites

- Python 3.8 or higher
- OCI CLI configured (for OCI Vault integration)
- Docker with MCP Gateway (optional, for full functionality)

### Quick Start

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone <repo-url>
   cd oci-vault-mcp-resolver
   ```

2. **Install dependencies**:
   ```bash
   pip3 install --user -r requirements.txt
   ```

3. **Start the web UI**:
   ```bash
   cd web
   ./start.sh
   ```

4. **Open your browser**:
   Navigate to `http://127.0.0.1:5000`

### Custom Configuration

Start with custom host and port:
```bash
./start.sh --host 0.0.0.0 --port 8080
```

Enable debug mode:
```bash
./start.sh --debug
```

Use environment variables:
```bash
export MCP_WEB_HOST=0.0.0.0
export MCP_WEB_PORT=8080
export FLASK_SECRET_KEY="your-secret-key-here"  # Recommended for production
./start.sh
```

**Security Note**: For production deployments, always set `FLASK_SECRET_KEY` to a secure random value to maintain session consistency across restarts.

## Docker Deployment

### Build and Run

Build the Docker image:
```bash
docker build -t mcp-gateway-web .
```

Run the container:
```bash
docker run -d \
  --name mcp-gateway-web \
  -p 5000:5000 \
  -v ~/.oci:/root/.oci:ro \
  -v ~/.cache/oci-vault-mcp:/root/.cache/oci-vault-mcp \
  mcp-gateway-web
```

### Docker Compose

Create a `docker-compose.yml`:
```yaml
version: '3.8'

services:
  mcp-web:
    build: .
    container_name: mcp-gateway-web
    ports:
      - "5000:5000"
    volumes:
      - ~/.oci:/root/.oci:ro
      - cache:/root/.cache/oci-vault-mcp
    environment:
      - MCP_WEB_HOST=0.0.0.0
      - MCP_WEB_PORT=5000
    restart: unless-stopped

volumes:
  cache:
```

Start with:
```bash
docker-compose up -d
```

## Usage Guide

### Dashboard

The dashboard provides an overview of your system:

1. **Status Cards**: Show the health of Docker MCP, OCI Vault, cache, and servers
2. **Configured Servers**: List all MCP servers in your configuration
3. **Quick Actions**: Common tasks like resolving secrets, clearing cache, and restarting gateway

### Marketplace

Browse and install MCP servers:

1. **Filter by Category**: Click category buttons to filter servers
2. **View Details**: Click on any server card to see full details
3. **Install**: Click "Add to Configuration" to add the server
4. **Configure Secrets**: Update the configuration with your actual OCI Vault references

Available categories:
- **Core**: Essential MCP servers (filesystem, etc.)
- **Development**: GitHub, GitLab, version control
- **Database**: PostgreSQL, MySQL, MongoDB
- **Monitoring**: Prometheus, Grafana
- **Communication**: Slack, Discord, email
- **Automation**: Puppeteer, Selenium

### Secrets Management

Manage OCI Vault secrets:

1. **View Cached Secrets**: See all secrets currently in cache
2. **Check Age**: Identify stale secrets that need refresh
3. **Clear Cache**: Force fresh fetch from OCI Vault
4. **URL Formats**: Learn about different OCI Vault reference formats

Supported URL formats:
```yaml
# Direct OCID (fastest)
oci-vault://ocid1.vaultsecret.oc1.region.xxx

# Compartment + Name (recommended)
oci-vault://ocid1.compartment.oc1..xxx/secret-name

# Vault + Name
oci-vault://ocid1.vault.oc1.region.xxx/secret-name
```

### Configuration Editor

Edit your MCP configuration:

1. **Load**: Fetch current configuration from Docker MCP
2. **Edit**: Make changes in the YAML editor
3. **Save**: Apply configuration to Docker MCP
4. **Resolve & Save**: Automatically resolve OCI Vault secrets before saving

Example configuration with secrets:
```yaml
servers:
  github:
    config:
      GITHUB_TOKEN: oci-vault://ocid1.compartment.oc1..xxx/github-token
  
  postgres:
    config:
      DB_HOST: localhost
      DB_PASSWORD: oci-vault://ocid1.compartment.oc1..xxx/db-password
```

## API Reference

The web UI exposes a REST API for programmatic access:

### Status Endpoints

**GET /api/status**
```json
{
  "docker_mcp": {
    "available": true,
    "version": "1.0.0"
  },
  "oci_vault": {
    "available": true,
    "version": "3.x.x"
  },
  "cache": {
    "enabled": true,
    "secret_count": 5
  }
}
```

### Configuration Endpoints

**GET /api/config** - Get current MCP configuration

**POST /api/config** - Update MCP configuration
```json
{
  "servers": {
    "my-server": {
      "config": {...}
    }
  }
}
```

**POST /api/config/resolve** - Resolve OCI Vault secrets
```json
{
  "servers": {
    "my-server": {
      "config": {
        "API_KEY": "oci-vault://..."
      }
    }
  }
}
```

### Catalog Endpoints

**GET /api/catalog** - Get MCP server catalog

**GET /api/catalog?category=Development** - Filter by category

**GET /api/catalog/{server_id}** - Get specific server details

### Secrets Endpoints

**GET /api/secrets** - List cached secrets

**POST /api/secrets/clear** - Clear secrets cache

### Server Endpoints

**GET /api/servers** - List configured servers

**POST /api/gateway/restart** - Restart MCP gateway

## Architecture

The web UI is built with:

- **Backend**: Flask (Python)
  - RESTful API design
  - Integration with OCI Vault resolver
  - Docker MCP command execution

- **Frontend**: Vanilla JavaScript + Modern CSS
  - No build step required
  - Responsive design
  - Real-time updates

- **Storage**: 
  - Local file cache for secrets
  - Docker MCP for configuration persistence

## Security Considerations

### Cache Security
- Cache files stored with 0600 permissions
- Located in `~/.cache/oci-vault-mcp/`
- Automatically secured on creation

### Network Security
- **CORS restricted to localhost origins only** (127.0.0.1, localhost)
- Default binding to 127.0.0.1 (localhost only)
- Use `--host 0.0.0.0` only in trusted networks
- Consider using a reverse proxy (nginx, Caddy) with HTTPS

### Authentication
- No built-in authentication (designed for trusted environments)
- Recommended: Use behind VPN or with reverse proxy authentication
- For production: Add OAuth2, OIDC, or basic auth via reverse proxy

### Command Execution Security
- **Command validation**: Only `docker` and `oci` commands allowed
- **Shell injection prevention**: `shell=False` enforced on all subprocess calls
- **Input sanitization**: XSS protection with HTML escaping on all user inputs

### Session Security
- **SECRET_KEY**: Set `FLASK_SECRET_KEY` environment variable for production
- Random key generated if not set (sessions reset on restart)

### OCI Credentials
- Never expose OCI config files via web UI
- Mount OCI config as read-only in Docker
- Use instance principals when possible

## Troubleshooting

### Web UI won't start

**Error**: `ModuleNotFoundError: No module named 'flask'`
```bash
pip3 install --user -r requirements.txt
```

**Error**: `Address already in use`
```bash
# Use a different port
./start.sh --port 8080
```

### Cannot connect to Docker MCP

**Issue**: Docker MCP not found
```bash
# Install Docker MCP or use web UI without Docker integration
# The UI will show warnings but still function for secrets management
```

### OCI Vault integration not working

**Issue**: OCI CLI not configured
```bash
# Configure OCI CLI
oci setup config

# Or use instance principals (on OCI VMs)
```

### Secrets not resolving

**Issue**: Check cache and permissions
```bash
# Clear cache
rm -rf ~/.cache/oci-vault-mcp/

# Check OCI CLI works
oci vault secret list --compartment-id YOUR_COMPARTMENT_ID
```

## Remote Development Use Cases

### SSH Development Server

Access the web UI from your local machine:
```bash
# On server: Start web UI
./start.sh --host 0.0.0.0 --port 5000

# On local machine: Create SSH tunnel
ssh -L 5000:localhost:5000 user@remote-server

# Open browser to http://localhost:5000
```

### Docker Devcontainer

Add to your `.devcontainer/docker-compose.yml`:
```yaml
services:
  dev:
    # ... your dev container config
    
  mcp-web:
    build: ../oci-vault-mcp-resolver
    ports:
      - "5000:5000"
    volumes:
      - ~/.oci:/root/.oci:ro
```

### GitHub Codespaces

Port forwarding is automatic! Just start the web UI and Codespaces will expose the port.

### Cloud VM (OCI, AWS, Azure)

Use instance principals for authentication:
```bash
# No OCI config needed!
./start.sh
```

## Development

### Project Structure

```
web/
├── app.py              # Flask backend application
├── start.sh            # Startup script
├── requirements.txt    # Python dependencies
├── static/
│   ├── css/
│   │   └── style.css   # Modern CSS styles
│   └── js/
│       └── app.js      # Frontend JavaScript
└── templates/
    └── index.html      # Main HTML template
```

### Adding New Features

1. **Backend**: Add new routes in `app.py`
2. **Frontend**: Update `app.js` for new functionality
3. **Styling**: Modify `style.css` for UI changes
4. **Catalog**: Update `MCP_CATALOG` in `app.py` to add servers

### Testing Locally

```bash
# Enable debug mode for auto-reload
./start.sh --debug

# Test API endpoints
curl http://localhost:5000/api/status

# Check logs for errors
```

## Contributing

Contributions welcome! Please:
1. Test your changes thoroughly
2. Follow existing code style
3. Update documentation
4. Submit a pull request

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
- GitHub Issues: <repo-url>/issues
- Documentation: See main README.md
- OCI Vault Docs: https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm

---

**Built with ❤️ for the MCP community**
