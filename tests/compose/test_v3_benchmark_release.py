"""Release gate: authenticated real-browser V3 benchmark acceptance."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from infrastructure.settings import redact_secrets
from tests.compose.conftest import (
    GenerationalStack,
    docker_cli,
    playwright_api,
    research_credentials_script,
    stack_api_logs,
)

pytestmark = pytest.mark.compose

_MARKER_KINDS = {
    "new_agents",
    "deaths",
    "migration",
    "teaching",
    "collective_project",
    "technology_spread",
    "cultural_differentiation",
    "office_succession",
}


@pytest.fixture(scope="module")
def benchmark(
    benchmark_stack: tuple[GenerationalStack, dict[str, Any]],
) -> tuple[GenerationalStack, dict[str, Any]]:
    return benchmark_stack


def _control(stack: GenerationalStack) -> dict[str, str]:
    return {"x-palimpsest-token": stack.control_token}


def _inspection(stack: GenerationalStack) -> dict[str, str]:
    return {"x-palimpsest-token": stack.inspection_token}


def _debug(stack: GenerationalStack) -> dict[str, str]:
    return {"x-palimpsest-token": stack.debug_token}


def test_benchmark_sources_are_populated(
    benchmark: tuple[GenerationalStack, dict[str, Any]],
) -> None:
    stack, manifest = benchmark
    run_id = str(manifest["run_id"])
    assert int(manifest["boundary_tick"]) == 160
    assert manifest["journal"]["tick_gaps"] == [], manifest["journal"]["tick_gaps"]
    assert manifest["journal"]["chain_breaks"] == [], manifest["journal"][
        "chain_breaks"
    ]
    assert int(manifest["readable_tick"]) == 160, manifest["journal"]["events_20_21"]
    assert (
        str(
            {
                "snapshots": manifest["journal"]["snapshots"],
                "commit_window": manifest["journal"]["commit_window"],
            }
        )
        + "\n--- API ---\n"
        + stack_api_logs(stack)
    )
    markers = {str(item["kind"]): item for item in manifest["markers"]}
    assert set(markers) == _MARKER_KINDS
    assert all(item["status"] == "available" for item in markers.values())
    assert len(str(manifest["matrix"]["schema_version"])) > 0
    assert str(manifest["matrix"]["schema_version"]) == "matrix-metric-summary-v1"
    assert len(manifest["child_run_ids"]) == 2

    with httpx.Client(base_url=stack.base_url, timeout=120.0) as client:
        demographics = client.get(
            f"/v1/simulations/{run_id}/observer/demographics",
            params={"tick": int(manifest["readable_tick"])},
            headers=_inspection(stack),
        )
        assert demographics.status_code == 200, demographics.text
        document = demographics.json()
        assert document["availability"] == "available"
        assert document["population"]["admitted"] >= 2
        assert document["population"]["max_generation_index"] >= 1

        families = client.get(
            f"/v1/simulations/{run_id}/lineage/families",
            params={"include_restricted": "true"},
            headers=_debug(stack),
        )
        assert families.status_code == 200
        names = {item["family"] for item in families.json()}
        assert {"genealogy", "knowledge", "narrative"} <= names

        catalogue = client.get(
            f"/v1/simulations/{run_id}/observer/civilization/catalogue",
            params={"evidence_class": "ANALYTICAL", "limit": 100},
            headers=_debug(stack),
        )
        assert catalogue.status_code == 200
        assert catalogue.json()["availability"] == "available"

        for child_run_id in manifest["child_run_ids"]:
            lineage = client.get(
                f"/v1/simulations/{child_run_id}/branch",
                headers=_inspection(stack),
            )
            assert lineage.status_code == 200
            assert lineage.json()["parent_run_id"] == run_id

        matrix = client.get(
            "/v1/research/matrices/v2-benchmark-suite/metric-summary",
            headers=_inspection(stack),
        )
        assert matrix.status_code == 200
        assert matrix.json()["schema_version"] == "matrix-metric-summary-v1"


def _research_url(stack: GenerationalStack, run_id: str, view: str, tick: int) -> str:
    return (
        f"{stack.base_url}/research/runs/{run_id}/{view}"
        f"?run_id={run_id}&tick={tick}"
    )


def _click_text(page: Any, text: str) -> None:
    # Exact ownership matters: "Diffusion" is both a tab label and part of the
    # panel heading, so a substring match would click the heading instead.
    page.get_by_text(text, exact=True).first.click(timeout=15000)


def test_godot_and_research_ui_replay_real_history(
    benchmark: tuple[GenerationalStack, dict[str, Any]],
) -> None:
    stack, manifest = benchmark
    run_id = str(manifest["run_id"])
    markers = manifest["markers"]
    published = manifest.get("publication", {}).get("civilization", {}).get(
        "published_ticks"
    ) or [int(manifest["readable_tick"])]
    overlay_tick = max(int(item) for item in published)
    console: list[str] = []
    requests: list[dict[str, str]] = []
    screenshots = stack.benchmark_root
    assert screenshots is not None

    with playwright_api()() as playwright:
        browser = playwright.chromium.launch(
            args=[
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
            ]
        )
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.on("console", lambda message: console.append(message.text))

            def _request(request: Any) -> None:
                if "/v1/" in request.url:
                    requests.append(
                        {
                            "method": request.method,
                            "path": request.url.split("?")[0],
                            "token": request.headers.get("x-palimpsest-token", ""),
                        }
                    )

            page.on("request", _request)
            for index, marker in enumerate(markers):
                tick = int(marker["tick"] or 0)
                page.goto(
                    f"{stack.base_url}/?run_id={run_id}&tick={tick}&debugger=1",
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(1200)
                assert f"tick={tick}" in page.url
                page.screenshot(
                    path=str(screenshots / f"godot-marker-{index}.png"),
                    full_page=False,
                )
            first_tick = int(markers[0]["tick"] or 0)
            last_tick = int(markers[-1]["tick"] or 0)
            page.goto(
                f"{stack.base_url}/?run_id={run_id}&tick={last_tick}",
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(600)
            assert f"tick={last_tick}" in page.url
            page.goto(
                f"{stack.base_url}/?run_id={run_id}&tick={first_tick}",
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(600)
            assert f"tick={first_tick}" in page.url
            page.goto(
                f"{stack.base_url}/?run_id={run_id}&tick={last_tick}",
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(600)
            assert f"tick={last_tick}" in page.url
            child_run_id = str(manifest["child_run_ids"][0])
            page.goto(
                f"{stack.base_url}/?run_id={child_run_id}&tick={last_tick}",
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(600)
            assert f"run_id={child_run_id}" in page.url
            assert all(item["method"] == "GET" for item in requests)

            page.add_init_script(research_credentials_script(stack))
            page.goto(
                _research_url(
                    stack, run_id, "population", int(manifest["readable_tick"])
                ),
                wait_until="networkidle",
            )
            assert page.get_by_text("Population and demographics").count() >= 1
            assert page.get_by_text("Living").count() >= 1
            page.screenshot(path=str(screenshots / "research-population.png"))

            page.goto(
                _research_url(
                    stack, run_id, "lineage", int(manifest["readable_tick"])
                ),
                wait_until="networkidle",
            )
            assert page.get_by_text("Qualified lineage explorer").count() >= 1
            assert page.get_by_text("Root candidates").count() >= 1
            assert page.get_by_text("objective", exact=True).count() >= 1
            page.screenshot(path=str(screenshots / "research-lineage.png"))

            page.goto(
                _research_url(stack, run_id, "technology", overlay_tick),
                wait_until="networkidle",
            )
            _click_text(page, "Diffusion")
            page.wait_for_timeout(500)
            assert page.get_by_text("Technology diffusion rows").count() >= 1
            page.screenshot(path=str(screenshots / "research-technology.png"))

            page.goto(
                _research_url(stack, run_id, "culture", overlay_tick),
                wait_until="networkidle",
            )
            _click_text(page, "Load captured culture overlays")
            page.wait_for_timeout(500)
            assert page.get_by_text("Cultural trait timelines").count() >= 1
            page.screenshot(path=str(screenshots / "research-culture.png"))

            page.goto(
                _research_url(
                    stack, run_id, "narratives", int(manifest["readable_tick"])
                ),
                wait_until="networkidle",
            )
            _click_text(page, "Load current narrative metadata")
            page.wait_for_timeout(500)
            assert page.get_by_text("Historical narrative lineage").count() >= 1
            page.screenshot(path=str(screenshots / "research-narratives.png"))

            page.goto(
                _research_url(stack, run_id, "institutions", overlay_tick),
                wait_until="networkidle",
            )
            _click_text(page, "Load institution timeline")
            page.wait_for_timeout(500)
            assert page.get_by_text("Institutions", exact=False).count() >= 1
            page.screenshot(path=str(screenshots / "research-institutions.png"))

            page.goto(
                _research_url(stack, run_id, "migration", overlay_tick),
                wait_until="networkidle",
            )
            _click_text(page, "Load migration window")
            page.wait_for_timeout(500)
            assert (
                page.get_by_text("Routes, regions and locations").count() >= 1
            )
            page.screenshot(path=str(screenshots / "research-migration.png"))

            page.goto(
                _research_url(
                    stack, run_id, "compare", int(manifest["readable_tick"])
                ),
                wait_until="networkidle",
            )
            inputs = page.locator("form input")
            inputs.nth(0).fill(str(manifest["child_run_ids"][0]))
            inputs.nth(1).fill(str(manifest["child_run_ids"][1]))
            page.locator("form").get_by_role(
                "button", name="Compare", exact=True
            ).click()
            page.wait_for_timeout(800)
            assert page.get_by_text("prefix coverage").count() >= 1
            page.screenshot(path=str(screenshots / "research-compare.png"))

            page.goto(
                _research_url(
                    stack, run_id, "population", int(manifest["readable_tick"])
                ),
                wait_until="networkidle",
            )
            page.reload(wait_until="networkidle")
            page.go_back(wait_until="networkidle")
            assert "view=compare" in page.url or "/compare" in page.url
            assert stack.debug_token not in page.url
            assert "token=" not in page.url
        except BaseException:
            pytest.fail(
                redact_secrets(
                    "\n".join(console[-300:])
                    + "\n--- API ---\n"
                    + stack_api_logs(stack)
                )
            )
        finally:
            page.close()
            browser.close()

    with httpx.Client(base_url=stack.base_url, timeout=60.0) as client:
        status = client.get(
            f"/v1/simulations/{run_id}", headers=_control(stack)
        )
    assert status.status_code == 200
    assert int(status.json().get("ticks_committed", 0)) == 160


def test_negative_credentials_do_not_render_private_domains(
    benchmark: tuple[GenerationalStack, dict[str, Any]],
) -> None:
    stack, manifest = benchmark
    run_id = str(manifest["run_id"])
    with httpx.Client(base_url=stack.base_url, timeout=60.0) as client:
        forbidden = client.get(
            f"/v1/simulations/{run_id}/lineage/families",
            params={"include_restricted": "true"},
        )
        assert forbidden.status_code in {401, 403}
        no_inspection = client.get(
            f"/v1/simulations/{run_id}/observer/demographics",
            params={"tick": int(manifest["readable_tick"])},
        )
        assert no_inspection.status_code in {401, 403}
    docker_cli()
