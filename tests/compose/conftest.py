"""Shared published-image fixtures for V2 and generational browser acceptance."""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from infrastructure.settings import redact_secrets

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "compose.yaml"
SEED_SCRIPT = ROOT / "tests" / "compose" / "seed_generational_evidence.py"


def docker_cli() -> str:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker CLI is not available")
    return docker


def playwright_api() -> Any:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright is not installed")
    return sync_playwright


def _database_image() -> str:
    for line in COMPOSE_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("image: pgvector/"):
            return stripped.split("image:", 1)[1].strip()
    raise AssertionError("database image pin missing")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(args: list[str], *, env: dict[str, str], check: bool = True) -> None:
    completed = subprocess.run(
        args, cwd=str(ROOT), env=env, check=False, capture_output=True, text=True
    )
    if check and completed.returncode != 0:
        pytest.fail(redact_secrets(completed.stdout + completed.stderr))


@dataclass(frozen=True, slots=True)
class GenerationalStack:
    project: str
    base_url: str
    image: str
    env: dict[str, str]
    lineage_root: Path
    control_token: str
    inspection_token: str
    debug_token: str
    lineage_enabled: bool


def _generational_stack(
    tmp_path: Path, *, lineage_enabled: bool
) -> Iterator[GenerationalStack]:
    image = os.environ.get("PALIMPSEST_API_IMAGE", "").strip()
    if not image:
        pytest.skip("PALIMPSEST_API_IMAGE is not set")
    docker = docker_cli()
    playwright_api()
    project = f"palimpsest-gen-{secrets.token_hex(4)}"
    port = str(_free_port())
    lineage_root = tmp_path / "lineage"
    lineage_root.mkdir()
    lineage_root.chmod(0o777)
    control = secrets.token_urlsafe(32)
    inspection = secrets.token_urlsafe(32)
    debug = secrets.token_urlsafe(32)
    env = os.environ.copy()
    env.update(
        {
            "PALIMPSEST_API_IMAGE": image,
            "PALIMPSEST_API_PUBLISH_PORT": port,
            "PALIMPSEST_ACCEPT_CONTROL": control,
            "PALIMPSEST_ACCEPT_INSPECTION": inspection,
            "PALIMPSEST_ACCEPT_DEBUG": debug,
            "PALIMPSEST_ACCEPT_AGENT_VISIBLE": secrets.token_urlsafe(32),
        }
    )
    override = tmp_path / "compose.override.yaml"
    dsn = "postgresql+asyncpg://palimpsest:palimpsest@db:5432/palimpsest_test"
    lines = [
        "services:",
        "  db:",
        "    environment:",
        '      POSTGRES_DB: "palimpsest_test"',
        "    healthcheck:",
        '      test: ["CMD-SHELL", "pg_isready -U palimpsest -d palimpsest_test"]',
        "  migrate:",
        "    environment:",
        f'      PALIMPSEST_DATABASE_URL: "{dsn}"',
        "  api:",
        "    environment:",
        f'      PALIMPSEST_DATABASE_URL: "{dsn}"',
        '      PALIMPSEST_API_AUTH_REQUIRED: "true"',
        '      PALIMPSEST_API_CONTROL_CREDENTIAL: "${PALIMPSEST_ACCEPT_CONTROL}"',
        '      PALIMPSEST_API_INSPECTION_CREDENTIAL: "${PALIMPSEST_ACCEPT_INSPECTION}"',
        "      PALIMPSEST_API_AGENT_VISIBLE_CREDENTIAL: "
        '"${PALIMPSEST_ACCEPT_AGENT_VISIBLE}"',
        '      PALIMPSEST_API_DEBUG_ENABLED: "true"',
        '      PALIMPSEST_API_DEBUG_CREDENTIAL: "${PALIMPSEST_ACCEPT_DEBUG}"',
    ]
    if lineage_enabled:
        lines.extend(
            [
                '      PALIMPSEST_LINEAGE_ROOT: "/srv/palimpsest/lineage"',
                "    volumes:",
                "      - type: bind",
                f"        source: {lineage_root}",
                "        target: /srv/palimpsest/lineage",
                "        read_only: true",
            ]
        )
    override.write_text("\n".join(lines) + "\n", encoding="utf-8")
    compose = [
        docker,
        "compose",
        "-p",
        project,
        "-f",
        str(COMPOSE_FILE),
        "-f",
        str(override),
    ]
    try:
        _run([docker, "pull", _database_image()], env=env)
        _run(
            [
                *compose,
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "180",
                "--pull",
                "never",
            ],
            env=env,
        )
        yield GenerationalStack(
            project=project,
            base_url=f"http://127.0.0.1:{port}",
            image=image,
            env=env,
            lineage_root=lineage_root,
            control_token=control,
            inspection_token=inspection,
            debug_token=debug,
            lineage_enabled=lineage_enabled,
        )
    except Exception:
        logs = subprocess.run(
            [*compose, "logs", "--no-color"],
            cwd=str(ROOT),
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        pytest.fail(redact_secrets(logs.stdout + logs.stderr))
    finally:
        _run(
            [*compose, "down", "--volumes", "--remove-orphans"],
            env=env,
            check=False,
        )
        if lineage_enabled:
            subprocess.run(
                [
                    docker,
                    "run",
                    "--rm",
                    "--user",
                    "root",
                    "-v",
                    f"{lineage_root}:/lineage",
                    "--entrypoint",
                    "sh",
                    image,
                    "-c",
                    "rm -rf /lineage/* /lineage/.[!.]* "
                    "/lineage/..?* 2>/dev/null || true",
                ],
                cwd=str(ROOT),
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )


@pytest.fixture
def published_generational_stack(
    tmp_path: Path,
) -> Iterator[GenerationalStack]:
    yield from _generational_stack(tmp_path, lineage_enabled=True)


@pytest.fixture
def published_generational_capture_off(
    tmp_path: Path,
) -> Iterator[GenerationalStack]:
    yield from _generational_stack(tmp_path, lineage_enabled=False)


def stack_api_logs(stack: GenerationalStack) -> str:
    docker = docker_cli()
    completed = subprocess.run(
        [
            docker,
            "compose",
            "-p",
            stack.project,
            "-f",
            str(COMPOSE_FILE),
            "logs",
            "--no-color",
            "api",
        ],
        cwd=str(ROOT),
        env=stack.env,
        check=False,
        capture_output=True,
        text=True,
    )
    return redact_secrets(completed.stdout + completed.stderr)


def seed_lineage(stack: GenerationalStack) -> str:
    docker = docker_cli()
    dsn = "postgresql+asyncpg://palimpsest:palimpsest@db:5432/palimpsest_test"
    args = [
        docker,
        "run",
        "--rm",
        "--network",
        f"{stack.project}_default",
        "-e",
        f"PALIMPSEST_DATABASE_URL={dsn}",
        "-e",
        "PALIMPSEST_ENVIRONMENT=production",
        "-v",
        f"{stack.lineage_root}:/lineage",
        "-v",
        f"{SEED_SCRIPT}:/acceptance/seed.py:ro",
        "--entrypoint",
        "/app/.venv/bin/python",
        stack.image,
        "/acceptance/seed.py",
        "--base-url",
        "http://api:8080",
        "--lineage-root",
        "/lineage",
        "--inspection-token",
        stack.inspection_token,
    ]
    completed = subprocess.run(
        args, cwd=str(ROOT), env=stack.env, check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        pytest.fail(redact_secrets(completed.stdout + completed.stderr))
    for line in reversed(completed.stdout.splitlines()):
        if line.strip().startswith("{"):
            return line.strip()
    pytest.fail(redact_secrets(completed.stdout + completed.stderr))
