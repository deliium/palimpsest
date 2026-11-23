# mypy: ignore-errors

"""Ecological resources documentation pins."""

from __future__ import annotations

from pathlib import Path

import pytest

from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    decode_ecological_resources,
)
from simulation.versioning import ECOLOGY_WRITE_PAIR_CODEC, ECOLOGY_WRITE_PAIR_EVENT
from world.events import EVENT_SCHEMA_REPLAY_V25

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_page_exists_and_readme_links() -> None:
    page = _read("docs/ecological-resources.md")
    assert page.startswith("# Ecological resources\n")
    assert _read("README.md").count("docs/ecological-resources.md") == 2


def test_required_headings_and_non_population_claim() -> None:
    page = _read("docs/ecological-resources.md")
    for heading in (
        "# Ecological resources",
        "## Scope",
        "## Configuration",
        "## Transition (one managed node per tick)",
        "## Perception and reads",
        "## Persistence and replay",
        "## Controlled demonstration",
        "## See Also",
    ):
        assert heading in page
    assert "population" in page.lower()
    assert "never" in page.lower()
    assert "species" in page.lower()
    assert "disasters" in page.lower()


def test_pins_and_example_decode() -> None:
    page = _read("docs/ecological-resources.md")
    assert "runner-config-v60" in page
    assert str(ECOLOGY_WRITE_PAIR_EVENT) in page
    assert ECOLOGY_WRITE_PAIR_CODEC in page
    assert EVENT_SCHEMA_REPLAY_V25 == ECOLOGY_WRITE_PAIR_EVENT == 25
    assert ECOLOGY_WRITE_PAIR_CODEC == "v23"
    assert "ecological_feedback" in V4_OWNED_CAPABILITY_FLAGS
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 11
    assert "disasters" not in V4_OWNED_CAPABILITY_FLAGS
    decoded = decode_ecological_resources(
        {
            "policy_id": ECOLOGICAL_RESOURCES_POLICY_ID,
            "nodes": [
                {
                    "resource_id": "res-water",
                    "minimum_capacity_tenths": 5,
                    "withdrawal_allowance_tenths": 0,
                    "recovery_tenths_per_idle_tick": 1,
                }
            ],
        }
    )
    assert decoded.policy_id == ECOLOGICAL_RESOURCES_POLICY_ID
    assert decoded.nodes[0].minimum_capacity_tenths == 5
