# Dockerfile for MCP Gateway Web UI with OCI Vault Integration

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt /app/requirements.txt
COPY web/requirements.txt /app/web-requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir -r /app/web-requirements.txt

# Copy application files
COPY oci_vault_resolver.py /app/
COPY web/ /app/web/

# Create cache directory
RUN mkdir -p /root/.cache/oci-vault-mcp && \
    chmod 700 /root/.cache/oci-vault-mcp

# Expose port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_WEB_HOST=0.0.0.0
ENV MCP_WEB_PORT=5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/status || exit 1

# Run the web application
WORKDIR /app/web
CMD ["python3", "app.py", "--host", "0.0.0.0", "--port", "5000"]
