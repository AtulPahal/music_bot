# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Install dependencies (without the project itself for caching)
RUN uv sync --frozen --no-install-project --no-dev

# Copy source
COPY . .

# Install the project in the existing venv
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy uv and the venv from builder
COPY --from=builder /app /app
COPY --from=builder /app/.venv /app/.venv

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "bot"]
