# syntax=docker/dockerfile:1
# Pinned Python 3.12.14 slim index digest (linux/amd64 and other published archs).
# Installs from uv.lock without re-resolution. Application logs go to stdout/stderr.
# Builder WORKDIR matches runtime so console-script shebangs remain valid.
# The editor runs only in the export stage. The runtime image receives the web files.

ARG PYTHON_IMAGE=python:3.12.14-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.10
ARG DEBIAN_IMAGE=debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251

FROM ${DEBIAN_IMAGE} AS observer-export-tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        unzip \
        libasound2 \
        libdbus-1-3 \
        libegl1 \
        libfontconfig1 \
        libgl1 \
        libx11-6 \
        libxcursor1 \
        libxext6 \
        libxi6 \
        libxinerama1 \
        libxkbcommon0 \
        libxrandr2 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY pyproject.toml ./
COPY scripts/export-observer-web.sh scripts/export-observer-web.sh
COPY clients/godot-observer ./clients/godot-observer
ARG PALIMPSEST_REVISION=unknown
ENV PALIMPSEST_REVISION=${PALIMPSEST_REVISION} \
    HOME=/tmp/export-home
RUN mkdir -p /tmp/export-home \
    && bash scripts/export-observer-web.sh /export

FROM scratch AS observer-export
COPY --from=observer-export-tools /export /

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS builder
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_DEV=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
RUN uv sync --frozen --no-dev --no-editable

FROM ${PYTHON_IMAGE} AS runtime
RUN groupadd --system --gid 1001 palimpsest \
    && useradd --system --uid 1001 --gid palimpsest --home-dir /app --create-home palimpsest
WORKDIR /app
ARG PALIMPSEST_REVISION=unknown
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PALIMPSEST_PRESENTATION_WEB_ROOT=/app/share/observer-web \
    PALIMPSEST_REVISION=${PALIMPSEST_REVISION}
COPY --from=builder --chown=palimpsest:palimpsest /app/.venv /app/.venv
COPY --from=builder --chown=palimpsest:palimpsest /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=palimpsest:palimpsest /app/alembic /app/alembic
COPY --from=observer-export --chown=palimpsest:palimpsest / /app/share/observer-web
USER palimpsest
EXPOSE 8080
CMD ["uvicorn", "api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
