# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim as base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build deps
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    gcc \
    make \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libpq-dev \
    bedtools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# Install Poetry
RUN pip install --no-cache-dir poetry

# Configure Poetry to put .venv inside /app
RUN poetry config virtualenvs.in-project true

# Copy Poetry project files
COPY poetry.lock pyproject.toml /app/

# Install dependencies (only)
RUN --mount=type=cache,target=/root/.cache/pip \
    poetry install --no-root --only main

# Copy application source
COPY epivar/ /app/epivar/
WORKDIR /app/epivar/

# Expose app port
EXPOSE 8000

# Change ownership
RUN mkdir -p /var/www/staticfiles/logos && chown -R appuser:appuser /var/www/staticfiles
RUN mkdir -p /opt/mediafiles && chown -R appuser:appuser /opt/mediafiles
RUN chown -R appuser:appuser /app

# Change user
USER appuser

# Run app via gunicorn
CMD ["./setup.sh"]