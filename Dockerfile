# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation and disable cache directory creation
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy package dependency definition files first for optimal layer caching
COPY pyproject.toml uv.lock ./

# Install project dependencies into virtual environment
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source code
COPY . .

# Install the application into the virtual environment
RUN uv sync --frozen --no-dev

# -----------------------------------------------------------------------------
# Final Production Runtime Stage
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runner

# Install essential system runtime dependencies for audio streaming and TLS
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Prevent Python from writing .pyc files and enable unbuffered output logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Create a non-root user and group for container security
RUN groupadd -g 10001 botuser && \
    useradd -u 10000 -g botuser -s /sbin/nologin -d /app botuser && \
    mkdir -p /app/data /app/logs && \
    chown -R botuser:botuser /app

# Copy the built virtual environment and application from the builder stage
COPY --from=builder --chown=botuser:botuser /app /app

USER botuser

CMD ["python", "-m", "bot"]
