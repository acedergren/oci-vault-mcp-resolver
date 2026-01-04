#!/bin/bash
# MCP Gateway Web UI Startup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║         MCP Gateway Web UI with OCI Vault Integration       ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Check if dependencies are installed
echo -e "${BLUE}Checking dependencies...${NC}"

if ! python3 -c "import flask" &> /dev/null; then
    echo -e "${YELLOW}Installing web dependencies...${NC}"
    pip3 install --user -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi

# Check for OCI CLI (optional but recommended)
if command -v oci &> /dev/null; then
    echo -e "${GREEN}✓ OCI CLI found${NC}"
else
    echo -e "${YELLOW}⚠ OCI CLI not found. Install it for OCI Vault integration.${NC}"
fi

# Check for Docker MCP (optional)
if command -v docker &> /dev/null && docker mcp --version &> /dev/null; then
    echo -e "${GREEN}✓ Docker MCP found${NC}"
else
    echo -e "${YELLOW}⚠ Docker MCP not found. Install it to manage MCP servers.${NC}"
fi

# Parse command line arguments
HOST="${MCP_WEB_HOST:-127.0.0.1}"
PORT="${MCP_WEB_PORT:-5000}"
DEBUG="${MCP_WEB_DEBUG:-false}"

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --debug)
            DEBUG="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --host HOST    Host to bind to (default: 127.0.0.1)"
            echo "  --port PORT    Port to bind to (default: 5000)"
            echo "  --debug        Enable debug mode"
            echo "  --help         Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  MCP_WEB_HOST   Override default host"
            echo "  MCP_WEB_PORT   Override default port"
            echo "  MCP_WEB_DEBUG  Enable debug mode (true/false)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo ""
echo -e "${BLUE}Starting web server...${NC}"
echo -e "  Dashboard: ${GREEN}http://${HOST}:${PORT}${NC}"
echo -e "  API Docs:  ${GREEN}http://${HOST}:${PORT}/api/status${NC}"
echo ""

# Start the Flask app
if [ "$DEBUG" = "true" ]; then
    python3 app.py --host "$HOST" --port "$PORT" --debug
else
    python3 app.py --host "$HOST" --port "$PORT"
fi
