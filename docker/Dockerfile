# Use the official Python slim image for a smaller footprint
FROM python:3.11-slim

# Install system dependencies, including git
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gnupg \
    supervisor \
    git && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js (version 20) and npm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m appuser

# Set the working directory
WORKDIR /app

# Copy and install backend dependencies
COPY fractalic/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the backend code and related files
COPY fractalic/fractalic.py /app/
COPY fractalic/fractalic_mcp_manager.py /app/
COPY fractalic/core/ /app/core/
COPY fractalic/ai_server/ /app/ai_server/
COPY fractalic/publisher/ /app/publisher/
COPY fractalic/tutorials/ /app/tutorials/
# Copy settings.toml if it exists (optional for local builds without user keys)
COPY fractalic/settings.toml* /app/
# Copy mcp_servers.json if it exists (optional for local builds)
COPY fractalic/mcp_servers.json* /app/
COPY fractalic/*.py /app/

# Copy and install frontend dependencies (fractalic-ui is at same level as fractalic in build context)
COPY fractalic-ui/package*.json /app/fractalic-ui/
RUN mkdir -p /app/fractalic-ui && \
    cd /app/fractalic-ui && \
    npm config set registry https://registry.npmjs.org/ && \
    npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm config set fetch-retries 5 && \
    (npm install --network-timeout=300000 || \
     echo "npm install failed - will try to run with existing node_modules or minimal setup")

# Copy the frontend code (files now directly in fractalic-ui root)
COPY fractalic-ui/ /app/fractalic-ui/

# Replace next.config.mjs with Docker-specific version for container networking
COPY next.config.docker.mjs /app/fractalic-ui/next.config.mjs

# Build the frontend for production
RUN cd /app/fractalic-ui && \
    ls -la && \
    (npm run build || echo "Frontend build failed - will try to run in dev mode")

# Create a logs directory and set ownership
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# Copy Supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Change ownership of the application directory to appuser
RUN chown -R appuser:appuser /app

# Set PYTHONPATH environment variable
ENV PYTHONPATH=/app

# Switch to the non-root user
USER appuser

# Expose the necessary ports
EXPOSE 8000 3000 8001 8002 8003 8004 5859

# Start Supervisor
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
