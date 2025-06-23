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
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the backend code and related files
COPY fractalic.py /app/
COPY fractalic_mcp_manager.py /app/
COPY core/ /app/core/
COPY ai_server/ /app/ai_server/
COPY publisher/ /app/publisher/
# Copy settings.toml if it exists (optional for local builds without user keys)
COPY settings.toml* /app/
# Copy mcp_servers.json if it exists (optional for local builds)
COPY mcp_servers.json* /app/
COPY *.py /app/

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
