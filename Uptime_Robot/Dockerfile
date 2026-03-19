# Multi-stage build for production
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Production stage
# -----------------------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY Uptime_Robot/ ./Uptime_Robot/
COPY docs/ ./docs/
COPY README.md CHANGELOG.md ./

# Create non-root user for security
RUN groupadd -r uptime && useradd -r -g uptime uptime \
    && mkdir -p /data /config /logs \
    && chown -R uptime:uptime /app /data /config /logs

# Environment variables
ENV PATH=/root/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    CONFIG_PATH=/config/config.json \
    DB_PATH=/data/sites.db \
    LOG_DIR=/logs

# Switch to non-root user
USER uptime

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Volumes for persistent data
VOLUME ["/data", "/config", "/logs"]

# Labels
LABEL maintainer="Uptime Monitor Team"
LABEL version="2.0.0"
LABEL description="Enterprise Uptime Monitoring with Backup & SSL"
LABEL org.opencontainers.image.source="https://github.com/ajjs1ajjs/Uptime-Monitor"

# Run the application
CMD ["python", "-m", "Uptime_Robot.main"]
