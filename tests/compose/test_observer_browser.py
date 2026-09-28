"""Browser smoke for a published image. Excluded from the default pytest run."""

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
from tests.compose.start_reference import start_reference

pytestmark = pytest.mark.compose

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "compose.yaml"
_LOGGER = logging.getLogger("palimpsest.compose.browser")
_NONTRIVIAL_WASM = 4096


def _docker() -> str:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker CLI is not available")
    return docker


def _playwright():
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


def _run(
    args: list[str],
    *,
    env: dict[str, str],
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


@pytest.fixture
def published_stack() -> Iterator[tuple[str, str, dict[str, str]]]:
    image = os.environ.get("PALIMPSEST_API_IMAGE", "").strip()
    if not image:
        pytest.skip("PALIMPSEST_API_IMAGE is not set")
    docker = _docker()
    _playwright()
    project = f"palimpsest-browser-{secrets.token_hex(4)}"
    port = str(_free_port())
    env = os.environ.copy()
    env["PALIMPSEST_API_IMAGE"] = image
    env["PALIMPSEST_API_PUBLISH_PORT"] = port
    try:
        _LOGGER.debug("compose_up_wait project=%s", project)
        database = _database_image()
        _run([docker, "pull", database], env=env)
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
                "--wait",
                "--wait-timeout",
                "180",
                "--pull",
                "never",
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


def _expect_asset(url: str, media_type: str, *, minimum: int = 1) -> bytes:
    response = httpx.get(url, timeout=30.0)
    assert response.status_code == 200
    content_type = response.headers["content-type"].split(";", 1)[0]
    assert content_type == media_type
    assert len(response.content) >= minimum
    return response.content


def test_published_observer_page_reaches_camp(
    published_stack: tuple[str, str, dict[str, str]],
) -> None:
    docker = _docker()
    sync_playwright = _playwright()
    project, port, env = published_stack
    base = f"http://127.0.0.1:{port}"
    page = _expect_asset(f"{base}/", "text/html")
    assert b"<html" in page.lower() or b"<!doctype html" in page.lower()
    _expect_asset(f"{base}/index.js", "text/javascript")
    _expect_asset(
        f"{base}/index.wasm",
        "application/wasm",
        minimum=_NONTRIVIAL_WASM,
    )
    _expect_asset(f"{base}/index.pck", "application/octet-stream")
    version = httpx.get(f"{base}/version", timeout=10.0)
    assert version.status_code == 200
    body = version.json()
    assert body["protocol_version"] == "observer-protocol-v1"
    assert body["export_engine"] == "4.7.2-stable"
    assert body["application_version"]
    assert body["revision"]
    run_id = start_reference(base)
    url = f"{base}/?run_id={run_id}"
    _LOGGER.debug("observer_browser_wait url=%s", url)
    console: list[str] = []
    hello = {"seen": False}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--use-gl=angle",
                    "--use-angle=swiftshader",
                    "--enable-unsafe-swiftshader",
                ],
            )
            page = browser.new_page()

            def _console(message) -> None:
                console.append(message.text)

            def _socket(ws) -> None:
                if "/observer/stream" not in ws.url:
                    return

                def _frame(payload) -> None:
                    text = payload if isinstance(payload, str) else payload.decode()
                    if '"kind"' in text and "hello" in text:
                        hello["seen"] = True

                ws.on("framereceived", _frame)

            page.on("console", _console)
            page.on("websocket", _socket)
            page.goto(url, wait_until="domcontentloaded")
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                joined = "\n".join(console)
                if "[observer.locations] map_built location_count=4" in joined:
                    break
                time.sleep(0.5)
            else:
                _LOGGER.error(
                    "observer_browser_failed reason_code=%s",
                    "map_timeout",
                )
                for line in console:
                    if "token" in line.lower():
                        continue
                    _LOGGER.error("observer_browser_console line=%s", line)
                pytest.fail("map_timeout")
            context = page.evaluate(
                """() => {
                    const canvas = document.querySelector('canvas');
                    if (!canvas) return null;
                    return canvas.getContext('webgl2');
                }"""
            )
            assert context is not None
            socket_deadline = time.monotonic() + 30
            while time.monotonic() < socket_deadline and not hello["seen"]:
                time.sleep(0.25)
            assert hello["seen"] is True
            browser.close()
    except Exception as exc:
        if "map_timeout" not in str(exc):
            _LOGGER.error(
                "observer_browser_failed reason_code=%s",
                type(exc).__name__,
            )
            for line in console:
                if "token" in line.lower():
                    continue
                _LOGGER.error("observer_browser_console line=%s", line)
        raise
    top = _run(
        [
            docker,
            "compose",
            "-p",
            project,
            "-f",
            str(COMPOSE_FILE),
            "top",
            "api",
        ],
        env=env,
    )
    assert "godot" not in top.stdout.lower()
    joined_logs = "\n".join(console)
    assert "token=" not in joined_logs
