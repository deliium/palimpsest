"""Opt-in Docker Compose stack checks.

Ordinary unit and integration runs never invoke Docker. Select these
tests with ``pytest -m compose``.
"""

from __future__ import annotations

import logging
import os
import secrets
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from infrastructure.settings import redact_secrets

pytestmark = pytest.mark.compose

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "compose.yaml"
DOCKERFILE = ROOT / "Dockerfile"
_LOGGER = logging.getLogger("palimpsest.compose.tests")


def _docker() -> str:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker CLI is not available")
    return docker


def _run(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        pytest.fail(redact_secrets(completed.stdout + completed.stderr))
    return completed


def test_dockerfile_pins_python_digest_and_frozen_lock() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "python:3.12.14-slim@sha256:" in text
    assert "uv sync --frozen --no-dev --no-editable" in text
    assert "UV_PROJECT_ENVIRONMENT=/app/.venv" in text
    assert "USER palimpsest" in text
    assert "--port" in text
    assert "8000" in text
    assert "curl" not in text.lower()


def test_compose_pins_pgvector_and_startup_order() -> None:
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    assert "pgvector/pgvector:0.8.6-pg17@sha256:" in text
    assert "condition: service_healthy" in text
    assert "condition: service_completed_successfully" in text
    assert "urllib.request" in text
    assert "curl" not in text.lower()
    assert "non-production" in text
    assert "not secret-safe" in text
    assert "PALIMPSEST_API_PUBLISH_PORT" in text


def test_compose_config_quiet() -> None:
    docker = _docker()
    _LOGGER.debug("compose_config_wait")
    env = os.environ.copy()
    env["PALIMPSEST_API_PUBLISH_PORT"] = "8000"
    _run(
        [docker, "compose", "-f", str(COMPOSE_FILE), "config", "--quiet"],
        env=env,
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def running_stack() -> Iterator[tuple[str, str, dict[str, str]]]:
    docker = _docker()
    project = f"palimpsest-smoke-{secrets.token_hex(4)}"
    port = str(_free_port())
    env = os.environ.copy()
    env["PALIMPSEST_API_PUBLISH_PORT"] = port
    try:
        _LOGGER.debug("compose_up_wait project=%s", project)
        _run(
            [
                docker,
                "compose",
                "-p",
                project,
                "-f",
                str(COMPOSE_FILE),
                "up",
                "-d",
                "--build",
                "--wait",
                "--wait-timeout",
                "180",
            ],
            env=env,
        )
        yield project, port, env
    except Exception:
        logs = _run(
            [
                docker,
                "compose",
                "-p",
                project,
                "-f",
                str(COMPOSE_FILE),
                "logs",
                "--no-color",
            ],
            env=env,
            check=False,
        )
        _LOGGER.error("compose_smoke_failed")
        pytest.fail(redact_secrets(logs.stdout + logs.stderr))
    finally:
        _LOGGER.debug("compose_down project=%s", project)
        _run(
            [
                docker,
                "compose",
                "-p",
                project,
                "-f",
                str(COMPOSE_FILE),
                "down",
                "--volumes",
                "--remove-orphans",
            ],
            env=env,
            check=False,
        )


def test_stack_health_and_non_root_api(
    running_stack: tuple[str, str, dict[str, str]],
) -> None:
    docker = _docker()
    project, port, env = running_stack
    inspect = _run(
        [
            docker,
            "compose",
            "-p",
            project,
            "-f",
            str(COMPOSE_FILE),
            "port",
            "api",
            "8000",
        ],
        env=env,
    )
    published = inspect.stdout.strip().rsplit(":", 1)[-1]
    assert published == port
    url = f"http://127.0.0.1:{published}/health"
    deadline = time.monotonic() + 30
    last_error = "health_unreached"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code == 200:
                assert response.json() == {"status": "ok"}
                break
            last_error = f"status={response.status_code}"
        except httpx.HTTPError as exc:
            last_error = type(exc).__name__
            time.sleep(0.5)
    else:
        _LOGGER.warning("degraded_health reason=%s", last_error)
        pytest.fail(redact_secrets(last_error))

    uid = _run(
        [
            docker,
            "compose",
            "-p",
            project,
            "-f",
            str(COMPOSE_FILE),
            "exec",
            "-T",
            "api",
            "python",
            "-c",
            "import os; print(os.getuid())",
        ],
        env=env,
    )
    assert uid.stdout.strip() == "1001"
