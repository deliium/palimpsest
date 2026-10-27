"""Published-image browser acceptance for civilization overlays/history."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest

from infrastructure.settings import redact_secrets
from tests.compose.conftest import (
    GenerationalStack,
    docker_cli,
    playwright_api,
    seed_civilization,
    stack_api_logs,
)
from tests.compose.start_generational import start_generational

pytestmark = pytest.mark.compose

_LOGGER = logging.getLogger("palimpsest.compose.civilization_browser")
_CONTROL_RE = re.compile(
    r"control id=(?P<id>\S+) x=(?P<x>[-\d.]+) y=(?P<y>[-\d.]+) "
    r"w=(?P<w>[-\d.]+) h=(?P<h>[-\d.]+)"
)


def _controls(console: list[str]) -> dict[str, tuple[float, float, float, float]]:
    found: dict[str, tuple[float, float, float, float]] = {}
    for line in console:
        match = _CONTROL_RE.search(line)
        if match is None:
            continue
        found[match.group("id")] = (
            float(match.group("x")),
            float(match.group("y")),
            float(match.group("w")),
            float(match.group("h")),
        )
    return found


def _click(page: Any, console: list[str], control_id: str) -> None:
    rect = _controls(console).get(control_id)
    if rect is None:
        pytest.fail(f"control missing id={control_id}")
    page.mouse.click(min(rect[0] + rect[2] / 2.0, 1270.0), rect[1] + rect[3] / 2.0)


def _authenticate(
    page: Any,
    console: list[str],
    stack: GenerationalStack,
    *,
    debug: bool = True,
) -> None:
    _wait_for(console, page, lambda text: "credentials_ready" in text)
    _click(page, console, "credentials_inspection")
    page.wait_for_timeout(250)
    page.keyboard.type(stack.inspection_token, delay=10)
    if debug:
        _click(page, console, "credentials_debug")
        page.wait_for_timeout(250)
        page.keyboard.type(stack.debug_token, delay=10)
    page.wait_for_timeout(150)
    _click(page, console, "credentials_apply")


def _heap_used(page: Any) -> int | None:
    """Chromium JS heap sample; ``None`` when the runtime does not expose it."""
    value = page.evaluate(
        "() => (performance && performance.memory)"
        " ? performance.memory.usedJSHeapSize : null"
    )
    return None if value is None else int(value)


def _wait_for(
    console: list[str],
    page: Any,
    predicate: Callable[[str], bool],
    *,
    timeout: float = 120.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate("\n".join(console)):
            return
        page.wait_for_timeout(100)
    pytest.fail(redact_secrets("\n".join(console[-100:])))


def _rendered_values(console: list[str]) -> dict[str, str]:
    for line in reversed(console):
        if "civilization_rendered" not in line:
            continue
        values: dict[str, str] = {}
        for token in line.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            values[key] = value
        if values:
            return values
    return {}


def _line_values(console: list[str], marker: str) -> dict[str, str]:
    for line in reversed(console):
        if marker not in line:
            continue
        values: dict[str, str] = {}
        for token in line.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            values[key] = value
        if values:
            return values
    return {}


def _wait_for_render(
    console: list[str],
    page: Any,
    predicate: Callable[[dict[str, str]], bool],
    *,
    timeout: float = 120.0,
) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        values = _rendered_values(console)
        if predicate(values):
            return values
        page.wait_for_timeout(100)
    pytest.fail(redact_secrets("\n".join(console[-100:])))


def _expect_asset(url: str, media_type: str, *, minimum: int = 1) -> None:
    response = httpx.get(url, timeout=30.0)
    assert response.status_code == 200
    assert response.headers["content-type"].split(";", 1)[0] == media_type
    assert len(response.content) >= minimum


def test_civilization_browser_history_and_assets(
    published_civilization_stack: GenerationalStack,
) -> None:
    stack = published_civilization_stack
    docker_cli()
    sync_playwright = playwright_api()
    base = stack.base_url
    _expect_asset(f"{base}/", "text/html")
    _expect_asset(f"{base}/index.js", "text/javascript")
    _expect_asset(f"{base}/index.wasm", "application/wasm", minimum=4096)
    _expect_asset(f"{base}/index.pck", "application/octet-stream")
    version = httpx.get(f"{base}/version", timeout=10.0).json()
    assert version["protocol_version"] == "observer-protocol-v1"
    assert version["export_engine"] == "4.7.2-stable"

    manifest = json.loads(seed_civilization(stack))
    run_id = str(manifest["run_id"])
    boundary = int(manifest["boundary_tick"])
    assert run_id.startswith("civ-real-")
    assert boundary == 256
    assert int(manifest["boundary_count"]) == 257
    if manifest["missing_categories"]:
        _LOGGER.warning(
            "civilization_real_producer_missing categories=%s",
            ",".join(str(item) for item in manifest["missing_categories"]),
        )

    inspection = {"x-palimpsest-token": stack.inspection_token}
    debug = {"x-palimpsest-token": stack.debug_token}
    map_response = httpx.get(
        f"{base}/v1/simulations/{run_id}/observer/civilization/map",
        params={"section": "locations", "tick": boundary, "limit": 100},
        headers=inspection,
        timeout=60.0,
    )
    assert map_response.status_code == 200
    assert map_response.json()["coverage"]["state"] != "disabled"
    catalogue = httpx.get(
        f"{base}/v1/simulations/{run_id}/observer/civilization/catalogue",
        params={"evidence_class": "ANALYTICAL", "limit": 100},
        headers=debug,
        timeout=60.0,
    )
    assert catalogue.status_code == 200
    assert catalogue.json()["availability"] == "available"
    assert catalogue.json()["boundaries"]
    markers = httpx.get(
        f"{base}/v1/simulations/{run_id}/observer/civilization/markers",
        params={
            "evidence_class": "OBJECTIVE",
            "from_tick": boundary - 10,
            "to_tick": boundary + 1,
            "limit": 100,
        },
        headers=inspection,
        timeout=60.0,
    )
    assert markers.status_code == 200, markers.text
    assert markers.json()["requested_window"]["end_tick"] == boundary + 1

    console: list[str] = []
    requests: list[dict[str, object]] = []
    layers = ",".join(
        (
            "population",
            "locations",
            "regions",
            "routes",
            "settlements",
            "trade",
            "projects",
            "records",
            "repositories",
            "culture",
            "technology",
            "migration",
            "social_groups",
            "institutions",
        )
    )
    url = (
        f"{base}/?run_id={run_id}&layout_id=regional-migration-ay-v1"
        f"&civilization_layers={layers}"
    )
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
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.on("console", lambda message: console.append(message.text))

            def _request(request: Any) -> None:
                if "/v1/" not in request.url:
                    return
                requests.append(
                    {
                        "method": request.method,
                        "path": urlsplit(request.url).path,
                        "query": urlsplit(request.url).query,
                        "token": request.headers.get("x-palimpsest-token", ""),
                    }
                )

            page.on("request", _request)
            page.goto(f"{url}&civilization_detail=full", wait_until="domcontentloaded")
            _authenticate(page, console, stack)
            _wait_for(console, page, lambda text: "map_built" in text)
            try:
                rendered = _wait_for_render(
                    console,
                    page,
                    lambda values: (
                        int(values.get("layers", "0")) >= 7
                        and int(values.get("locations", "0")) > 0
                        and int(values.get("regions", "0")) > 0
                        and int(values.get("routes", "0")) > 0
                        and int(values.get("settlements", "0")) > 0
                        and int(values.get("repositories", "0")) > 0
                        and int(values.get("records", "0")) > 0
                    ),
                )
            except BaseException:
                pytest.fail(
                    redact_secrets(
                        "\n".join(console[-200:])
                        + "\n--- REQUESTS ---\n"
                        + json.dumps(requests[-100:], indent=2)
                    )
                )
            page.screenshot(
                path=str(stack.civilization_root.parent / "civilization.png")
            )
            full_digest = rendered["digest"]

            # Warmed local control-to-visible busy/cleared feedback budget.
            def _feedback_count() -> int:
                return sum(
                    1
                    for line in console
                    if "civilization_layer " in line
                    or "civilization_layer_cleared" in line
                    or "civilization_rendered" in line
                )

            for _ in range(2):
                before = _feedback_count()
                _click(page, console, "civilization_population_toggle")
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline and _feedback_count() == before:
                    page.wait_for_timeout(10)
            timings: list[float] = []
            for _ in range(20):
                before = _feedback_count()
                started = time.monotonic()
                _click(page, console, "civilization_population_toggle")
                deadline = started + 2.0
                while time.monotonic() < deadline and _feedback_count() == before:
                    page.wait_for_timeout(10)
                timings.append((time.monotonic() - started) * 1000.0)
            p95 = sorted(timings)[18]
            assert p95 <= 250.0, f"p95_ms={p95:.1f} timings={timings}"
            _LOGGER.info(
                "[observer.browser] civilization_control_to_visible "
                "samples=%s p95_ms=%.1f max_ms=%.1f warm=warm",
                len(timings),
                p95,
                max(timings),
            )
            console.clear()
            page.goto(
                f"{url}&civilization_detail=aggregate",
                wait_until="domcontentloaded",
            )
            _authenticate(page, console, stack)
            _wait_for(console, page, lambda text: "map_built" in text)
            aggregate = _wait_for_render(
                console,
                page,
                lambda values: (
                    int(values.get("layers", "0")) >= 7
                    and int(values.get("locations", "0")) > 0
                    and int(values.get("regions", "0")) > 0
                    and int(values.get("routes", "0")) > 0
                    and int(values.get("settlements", "0")) > 0
                    and int(values.get("repositories", "0")) > 0
                    and int(values.get("records", "0")) > 0
                    and values.get("lod") == "aggregate"
                ),
            )
            assert aggregate["digest"] == full_digest, (
                f"full={rendered} aggregate={aggregate}"
            )
            console.clear()
            heap_before = _heap_used(page)
            page.goto(
                f"{base}/?run_id={run_id}&layout_id=regional-migration-ay-v1"
                "&civilization_detail=full&civilization_seek_cycles=50",
                wait_until="domcontentloaded",
            )
            _authenticate(page, console, stack, debug=False)
            _wait_for(console, page, lambda text: "map_built" in text)
            _wait_for(
                console,
                page,
                lambda text: "civilization_seeks_done" in text,
                timeout=120.0,
            )
            seeks = _line_values(console, "civilization_seeks_done")
            assert int(seeks["count"]) == 50
            assert int(seeks["inflight"]) <= 2
            assert int(seeks["queued"]) <= 14
            assert int(seeks["states"]) <= 14
            heap_after = _heap_used(page)
            heap_delta = (
                None
                if heap_before is None or heap_after is None
                else heap_after - heap_before
            )
            _LOGGER.info(
                "[observer.browser] civilization_seek_playback "
                "count=%s elapsed_ms=%s inflight=%s queued=%s states=%s "
                "heap_before=%s heap_after=%s heap_delta=%s warm=warm",
                seeks["count"],
                seeks["elapsed_ms"],
                seeks["inflight"],
                seeks["queued"],
                seeks["states"],
                heap_before,
                heap_after,
                heap_delta,
            )
            browser.close()
    except BaseException:
        pytest.fail(
            redact_secrets(
                "\n".join(console[-400:]) + "\n--- API ---\n" + stack_api_logs(stack)
            )
        )

    assert requests
    assert all(item["method"] == "GET" for item in requests)
    assert any("/observer/civilization/map" in str(item["path"]) for item in requests)
    assert all(
        stack.debug_token != item["token"]
        for item in requests
        if "/observer/civilization/map" in str(item["path"])
    )
    assert any(
        "/observer/civilization/overlays" in str(item["path"]) for item in requests
    )
    assert int(rendered["locations"]) > 0
    assert int(rendered["settlements"]) > 0
    assert int(rendered["public_acts"]) > 0
    assert int(rendered["repositories"]) > 0
    assert int(rendered["records"]) > 0


def test_capture_off_browser_remains_objective_only(
    published_civilization_capture_off: GenerationalStack,
) -> None:
    stack = published_civilization_capture_off
    docker_cli()
    sync_playwright = playwright_api()
    expectation = start_generational(
        stack.base_url,
        control_token=stack.control_token,
        inspection_token=stack.inspection_token,
    )
    inspection = {"x-palimpsest-token": stack.inspection_token}
    catalogue = httpx.get(
        f"{stack.base_url}/v1/simulations/{expectation.run_id}/observer/civilization/catalogue",
        params={"evidence_class": "ANALYTICAL"},
        headers=inspection,
        timeout=30.0,
    )
    assert catalogue.status_code in {401, 403, 404}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
            ],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        console: list[str] = []
        page.on("console", lambda message: console.append(message.text))
        page.goto(
            f"{stack.base_url}/?run_id={expectation.run_id}",
            wait_until="domcontentloaded",
        )
        try:
            _authenticate(page, console, stack, debug=False)
            _wait_for(console, page, lambda text: "map_built" in text)
        finally:
            browser.close()
