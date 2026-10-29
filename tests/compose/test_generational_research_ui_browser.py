"""Browser acceptance for the generational Research UI panels.

Required release runs use the shared authenticated benchmark stack, so the
shipped image and its real produced history determine the result. A local
convenience mode may instead point ``PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL``
and ``PALIMPSEST_COMPOSE_RESEARCH_RUN_ID`` at an already-running API; that mode
never determines required release results.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest

from tests.compose.conftest import (
    GenerationalStack,
    playwright_api,
    research_credentials_script,
)

pytestmark = pytest.mark.compose

PANELS = (
    ("population", "Population and demographics"),
    ("cohorts", "Within-run cohort comparison"),
    ("lineage", "Qualified lineage explorer"),
    ("teaching", "Teacher / student networks"),
    ("technology", "Technology lineage and diffusion"),
    ("culture", "Cultural trait timelines"),
    ("language", "Vocabulary, semantics and current meaning"),
    ("narratives", "Historical narrative lineage"),
    ("migration", "Migration flows"),
    ("economy", "Economic exchange networks"),
    ("projects", "Collective project history"),
    ("institutions", "Institutions"),
)


_Target = tuple[str, str, str | None]


@pytest.fixture(scope="module")
def research_target(request: pytest.FixtureRequest) -> Iterator[_Target]:
    external = os.environ.get("PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL", "").strip()
    if external:
        run_id = os.environ.get("PALIMPSEST_COMPOSE_RESEARCH_RUN_ID", "").strip()
        if not run_id:
            pytest.skip("PALIMPSEST_COMPOSE_RESEARCH_RUN_ID unset")
        yield external.rstrip("/"), run_id, None
        return
    fixture: tuple[GenerationalStack, dict[str, Any]] = request.getfixturevalue(
        "benchmark_stack"
    )
    stack, manifest = fixture
    yield (
        stack.base_url,
        str(manifest["run_id"]),
        research_credentials_script(stack),
    )


def _open(page: Any, credentials: str | None) -> None:
    if credentials is not None:
        page.add_init_script(credentials)


def test_grouped_research_panels_are_reachable(
    research_target: _Target,
) -> None:
    base, run_id, credentials = research_target
    with playwright_api()() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        _open(page, credentials)
        try:
            for view, heading in PANELS:
                page.goto(
                    f"{base}/research/runs/{run_id}/{view}?run_id={run_id}",
                    wait_until="networkidle",
                )
                assert page.locator("h1", has_text=heading).count() >= 1
                assert "later implementation task" not in page.content()
        finally:
            page.close()
            browser.close()


def test_workflow_preserves_tick_across_generational_panels(
    research_target: _Target,
) -> None:
    base, run_id, credentials = research_target
    headings = dict(PANELS)
    with playwright_api()() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        _open(page, credentials)
        try:
            for view, _heading in PANELS:
                page.goto(
                    f"{base}/research/runs/{run_id}/{view}?run_id={run_id}&tick=0",
                    wait_until="networkidle",
                )
                assert page.locator("h1", has_text=headings[view]).count() >= 1
                assert "tick=0" in page.url
                assert "later implementation task" not in page.content()
                assert "token=" not in page.url
        finally:
            page.close()
            browser.close()


def test_direct_link_back_forward_and_reload_preserve_tick(
    research_target: _Target,
) -> None:
    base, run_id, credentials = research_target
    with playwright_api()() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        _open(page, credentials)
        try:
            page.goto(
                f"{base}/research/runs/{run_id}/population?run_id={run_id}&tick=0",
                wait_until="networkidle",
            )
            page.goto(
                f"{base}/research/runs/{run_id}/language?run_id={run_id}&tick=0",
                wait_until="networkidle",
            )
            page.go_back(wait_until="networkidle")
            assert "population" in page.url
            page.reload(wait_until="networkidle")
            assert "tick=0" in page.url
        finally:
            page.close()
            browser.close()
