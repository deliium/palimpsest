"""Opt-in browser acceptance for the generational Research UI.

Skips unless ``PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL`` points at a running API
that serves the prebuilt SPA at ``/research/``. The harness uses the existing
Playwright fixture and never asserts emergent science from constructed data.
"""

from __future__ import annotations

import os

import pytest

from tests.compose.conftest import playwright_api

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


def _base_url() -> str:
    base = os.environ.get("PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL", "").strip()
    if not base:
        pytest.skip("PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL unset")
    return base.rstrip("/")


def _run_id() -> str:
    value = os.environ.get("PALIMPSEST_COMPOSE_RESEARCH_RUN_ID", "").strip()
    if not value:
        pytest.skip("PALIMPSEST_COMPOSE_RESEARCH_RUN_ID unset")
    return value


def test_grouped_research_panels_are_reachable() -> None:
    base = _base_url()
    run_id = _run_id()
    with playwright_api() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
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


def test_workflow_preserves_tick_across_generational_panels() -> None:
    base = _base_url()
    run_id = _run_id()
    headings = dict(PANELS)
    with playwright_api() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
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


def test_direct_link_back_forward_and_reload_preserve_tick() -> None:
    base = _base_url()
    run_id = _run_id()
    with playwright_api() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
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
