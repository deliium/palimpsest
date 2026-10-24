"""Published-image browser acceptance for the generational observer."""

from __future__ import annotations

import json
import logging
import re
import time
from urllib.parse import urlsplit

import httpx
import pytest

from infrastructure.settings import redact_secrets
from tests.compose.conftest import (
    GenerationalStack,
    docker_cli,
    playwright_api,
    seed_lineage,
)
from tests.compose.start_generational import start_generational

pytestmark = pytest.mark.compose

_LOGGER = logging.getLogger("palimpsest.compose.generational_browser")
_CONTROL_RE = re.compile(
    r"control id=(?P<id>\S+) x=(?P<x>[-\d.]+) y=(?P<y>[-\d.]+) "
    r"w=(?P<w>[-\d.]+) h=(?P<h>[-\d.]+)"
)


def _expect_asset(url: str, media_type: str, *, minimum: int = 1) -> None:
    response = httpx.get(url, timeout=30.0)
    assert response.status_code == 200
    assert response.headers["content-type"].split(";", 1)[0] == media_type
    assert len(response.content) >= minimum


def _controls(
    console: list[str],
) -> dict[str, tuple[float, float, float, float]]:
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


def _wait_for(console: list[str], page, predicate, *, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate("\n".join(console)):
            return
        page.wait_for_timeout(100)
    pytest.fail(redact_secrets("\n".join(console[-80:])))


def _click(page, console: list[str], control_id: str) -> None:
    rect = _controls(console).get(control_id)
    if rect is None:
        pytest.fail(f"control missing id={control_id}")
    x = rect[0] + 8.0 if control_id.endswith("_toggle") else rect[0] + rect[2] / 2.0
    page.mouse.click(min(x, 1270.0), rect[1] + rect[3] / 2.0)


@pytest.mark.xfail(
    strict=False,
    reason="Generational browser fetch gate unresolved; release blocker.",
)
def test_generational_browser_population_and_credentials(
    published_generational_stack: GenerationalStack,
) -> None:
    stack = published_generational_stack
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

    expectation = start_generational(
        base,
        control_token=stack.control_token,
        inspection_token=stack.inspection_token,
    )
    manifest = seed_lineage(
        stack, run_id=expectation.run_id, boundary_tick=expectation.boundary_tick
    )
    assert expectation.run_id in manifest
    evidence = json.loads(manifest)

    inspection = {"x-palimpsest-token": stack.inspection_token}
    debug = {"x-palimpsest-token": stack.debug_token}
    demographics = httpx.get(
        f"{base}/v1/simulations/{expectation.run_id}/observer/demographics",
        params={"tick": expectation.boundary_tick},
        headers=inspection,
        timeout=30.0,
    )
    assert demographics.status_code == 200
    assert demographics.json()["population"]["admitted"] == expectation.admitted
    markers = httpx.get(
        f"{base}/v1/simulations/{expectation.run_id}/observer/generation-markers",
        params={"tick": expectation.boundary_tick},
        headers=inspection,
        timeout=30.0,
    )
    assert markers.status_code == 200
    assert markers.json()["markers"]
    participants = httpx.get(
        f"{base}/v1/simulations/{expectation.run_id}"
        "/lineage/mentorship/participants",
        params={
            "evidence_class": "subjective",
            "owner_id": evidence["founder"],
            "agent_id": evidence["child"],
            "role": "learner",
            "boundary_tick": expectation.boundary_tick,
        },
        headers=debug,
        timeout=30.0,
    )
    assert participants.status_code == 200
    assert participants.json()["items"]
    assert participants.json()["items"][0]["owner_id"] == evidence["founder"]
    genealogy = httpx.get(
        f"{base}/v1/simulations/{expectation.run_id}/lineage/genealogy/nodes",
        params={
            "evidence_class": "objective",
            "boundary_tick": expectation.boundary_tick,
        },
        headers=inspection,
        timeout=30.0,
    )
    assert genealogy.status_code == 200
    assert genealogy.json()["items"]

    console: list[str] = []
    requests: list[dict[str, object]] = []
    url = f"{base}/?run_id={expectation.run_id}"
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

            def _request(request) -> None:
                if "/v1/" not in request.url:
                    return
                requests.append(
                    {
                        "method": request.method,
                        "path": urlsplit(request.url).path,
                        "token": request.headers.get("x-palimpsest-token", ""),
                    }
                )

            page.on("request", _request)
            page.goto(url, wait_until="domcontentloaded")
            _wait_for(console, page, lambda text: "credentials_ready" in text)
            page.wait_for_timeout(500)
            page.screenshot(
                path=str(stack.lineage_root.parent / "pre_credentials.png")
            )
            controls = _controls(console)
            assert "credentials_inspection" in controls
            assert "credentials_apply" in controls
            _wait_for(console, page, lambda text: "map_built" in text)
            page.wait_for_timeout(300)
            controls = _controls(console)
            assert "population_toggle" in controls
            _click(page, console, "population_toggle")
            page.keyboard.press("space")
            _wait_for(console, page, lambda text: "demographics_rendered" in text)
            joined = "\n".join(console)
            expected = (
                f"demographics_rendered living={expectation.living} "
                f"admitted={expectation.admitted} dead={expectation.dead} "
                f"max_generation={expectation.max_generation_index}"
            )
            if expected not in joined:
                rendered = [
                    line for line in console if "demographics_rendered" in line
                ]
                pytest.fail(
                    f"rendered_mismatch expected={expected} "
                    f"actual={rendered[-1] if rendered else 'missing'}"
                )
            page.screenshot(path=str(stack.lineage_root.parent / "generational.png"))
            browser.close()
    except Exception:
        pytest.fail(redact_secrets("\n".join(console[-400:])))

    demographic_requests = [
        item
        for item in requests
        if str(item["path"]).endswith("/observer/demographics")
    ]
    assert demographic_requests
    assert all(item["method"] == "GET" for item in requests)
    assert any(item["token"] == stack.inspection_token for item in demographic_requests)
    assert all(
        stack.debug_token != item["token"]
        for item in requests
        if str(item["path"]).endswith("/observer/demographics")
    )


def test_generational_browser_capture_off_keeps_objective_playback(
    published_generational_capture_off: GenerationalStack,
) -> None:
    stack = published_generational_capture_off
    expectation = start_generational(
        stack.base_url,
        control_token=stack.control_token,
        inspection_token=stack.inspection_token,
    )
    inspection = {"x-palimpsest-token": stack.inspection_token}
    response = httpx.get(
        f"{stack.base_url}/v1/simulations/{expectation.run_id}/observer/demographics",
        params={"tick": expectation.boundary_tick},
        headers=inspection,
        timeout=30.0,
    )
    assert response.status_code == 200
    lineage = httpx.get(
        f"{stack.base_url}/v1/simulations/{expectation.run_id}/lineage/families",
        headers=inspection,
        timeout=30.0,
    )
    assert lineage.status_code == 503
    assert lineage.json()["code"] == "lineage_disabled"
