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

# Copy backend code to /fractalic directory
COPY fractalic/ /fractalic/

# Copy and install backend dependencies
RUN pip install --no-cache-dir -r /fractalic/requirements.txt

# Copy and install frontend dependencies (fractalic-ui at same level as fractalic)
COPY fractalic-ui/package*.json /fractalic-ui/
RUN mkdir -p /fractalic-ui && \
    cd /fractalic-ui && \
    npm config set registry https://registry.npmjs.org/ && \
    npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm config set fetch-retries 5 && \
    (npm install --network-timeout=300000 || \
     echo "npm install failed - will try to run with existing node_modules or minimal setup")

# Copy the frontend code to same level as fractalic
COPY fractalic-ui/ /fractalic-ui/

# Replace next.config.mjs with Docker-specific version for container networking
# This MUST come after copying fractalic-ui/ to ensure it doesn't get overwritten
COPY next.config.docker.mjs /fractalic-ui/next.config.mjs

# Set working directory to fractalic for backend operations
WORKDIR /fractalic

# Skip npm run build - we use npm run dev in supervisord anyway
# This makes Docker builds much faster since production build is unused

# Create a logs directory and set ownership
RUN mkdir -p /fractalic/logs && chown -R appuser:appuser /fractalic/logs

# Copy Supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Change ownership of both application directories to appuser
RUN chown -R appuser:appuser /fractalic /fractalic-ui

# Set PYTHONPATH environment variable to fractalic directory
ENV PYTHONPATH=/fractalic

# Switch to the non-root user
USER appuser

# Expose the necessary ports
EXPOSE 8000 3000 8001 8002 8003 8004 5859

# Start Supervisor
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
