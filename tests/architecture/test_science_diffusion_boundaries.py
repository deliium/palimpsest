# mypy: ignore-errors
"""Science-diffusion layers keep analysis, authority, API and client boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from simulation.v4_architecture import V4_CONTEXTS

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"


def _text(relative: str) -> str:
    return (_SRC / relative).read_text(encoding="utf-8")


def test_analysis_modules_import_no_live_or_outer_layer() -> None:
    for relative in (
        "analysis/science_diffusion_contract.py",
        "analysis/science_diffusion_lineage.py",
        "analysis/science_diffusion_metrics.py",
    ):
        source = _text(relative)
        for forbidden in (
            "experiments",
            "api",
            "persistence",
            "infrastructure",
            "observer",
            "agents",
            "simulation",
        ):
            assert f"import {forbidden}" not in source, (relative, forbidden)
            assert f"from {forbidden}" not in source, (relative, forbidden)


def test_simulation_contracts_import_no_analysis_or_outer_layer() -> None:
    for relative in (
        "simulation/science_diffusion_models.py",
        "simulation/science_diffusion_codec.py",
        "simulation/science_diffusion_paging.py",
        "simulation/science_diffusion_ports.py",
    ):
        source = _text(relative)
        for forbidden in (
            "analysis",
            "experiments",
            "api",
            "persistence",
            "infrastructure",
            "observer",
            "agents",
        ):
            assert f"import {forbidden}" not in source, (relative, forbidden)
            assert f"from {forbidden}" not in source, (relative, forbidden)


def test_api_and_adapter_do_not_import_producer_or_analysis() -> None:
    for relative in (
        "api/routes/science_diffusion.py",
        "api/science_diffusion_cursor.py",
        "persistence/science_diffusion_filesystem.py",
    ):
        source = _text(relative)
        for forbidden in (
            "experiments.science_diffusion_publication",
            "analysis.science_diffusion_lineage",
            "analysis.science_diffusion_metrics",
        ):
            assert forbidden not in source, (relative, forbidden)


def test_no_new_objective_event_or_command_is_created() -> None:
    for relative in (
        "experiments/science_diffusion_scenario.py",
        "experiments/science_diffusion_publication.py",
        "experiments/science_diffusion_carriers.py",
        "analysis/science_diffusion_lineage.py",
    ):
        source = _text(relative)
        for forbidden in (
            "AgentCommand(",
            "ActionSubmission(",
            "WorldEngine",
            "WorldState",
            "class WorldEvent",
        ):
            assert forbidden not in source, (relative, forbidden)


def test_current_v4_pins_are_unchanged() -> None:
    assert METRIC_FAMILY_COUNT == 275
    assert len(V4_CONTEXTS) == 17
    from simulation.runner_models import V4CapabilityFlags

    assert len(V4CapabilityFlags.__dataclass_fields__) == 12
    from analysis.specifications import metric_specification

    for family in (
        "science_diffusion_channels",
        "science_diffusion_fidelity",
        "science_diffusion_persistence",
        "science_diffusion_genealogy",
    ):
        assert metric_specification(family).family_id.value == family
