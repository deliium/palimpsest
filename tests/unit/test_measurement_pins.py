# mypy: ignore-errors

"""V4-29 current pins and documentation contract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.persistence import (
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
    PENDING_FINALIZATION_ACCEPTED_VERSIONS,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V57,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
)
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
)
from world.actions import AgentCommand
from world.events import SUPPORTED_EVENT_SCHEMA_VERSIONS

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_current_version_and_count_pins() -> None:
    assert RUNNER_SCHEMA_VERSION_V57 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert 28 in SUPPORTED_EVENT_SCHEMA_VERSIONS
    assert "v26" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "finalization-command-v3" in PENDING_FINALIZATION_ACCEPTED_VERSIONS
    assert len(get_args(AgentCommand)) == 45
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert METRIC_FAMILY_COUNT == 262
    assert len(V4_CONTEXTS) == 17
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"


def test_measurement_page_and_readme_index_link() -> None:
    page = (ROOT / "docs/measurement-instruments.md").read_text()
    for token in (
        "measurement-instruments.v1",
        "runner-config-v57",
        "event 28",
        "v26",
        "measurement-state-v1",
        "msr_v1",
        "ambient_temperature",
        "resource_amount",
        "elapsed_duration",
        "travel_time_estimate",
        "load_category",
    ):
        assert token in page
    readme = (ROOT / "README.md").read_text()
    assert "(docs/measurement-instruments.md)" in readme


def test_measurement_page_relative_links_resolve() -> None:
    page = ROOT / "docs/measurement-instruments.md"
    text = page.read_text()
    links = re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", text)
    for link in links:
        if link.startswith(("http://", "https://", "mailto:")):
            continue
        assert (page.parent / link).resolve().exists(), link


def test_current_catalog_pin_is_not_stale_in_measurement_docs() -> None:
    for path in (
        ROOT / "docs/configuration.md",
        ROOT / "docs/persistence.md",
        ROOT / "docs/architecture.md",
    ):
        text = path.read_text()
        assert "Current catalog: 250 metric families" not in text
