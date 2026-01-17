# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim AS base

ARG APP_UID=10001
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libpq-dev \
    samtools \
    bedtools \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid ${APP_UID} \
    appuser

# Pin poetry for reproducibility
RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.in-project true

COPY poetry.lock pyproject.toml /app/

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --no-root

# Copy app
COPY epivar/ /app/epivar/
WORKDIR /app/epivar

# Chenge ownership & chan gemode
RUN chmod +x /app/epivar/setup.sh \
 && chown -R appuser:appuser /app

EXPOSE 8000

USER appuser
CMD ["./setup.sh"]
