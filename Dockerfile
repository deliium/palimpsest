# syntax=docker/dockerfile:1
# Pinned Python 3.12.14 slim index digest (linux/amd64 and other published archs).
# Installs from uv.lock without re-resolution. Application logs go to stdout/stderr.
# Builder WORKDIR matches runtime so console-script shebangs remain valid.

ARG PYTHON_IMAGE=python:3.12.14-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.10

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
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
COPY --from=builder --chown=palimpsest:palimpsest /app/.venv /app/.venv
COPY --from=builder --chown=palimpsest:palimpsest /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=palimpsest:palimpsest /app/alembic /app/alembic
USER palimpsest
EXPOSE 8080
CMD ["uvicorn", "api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
