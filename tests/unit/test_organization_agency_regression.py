"""Cross-surface V4-05 pins and flags-off behavior."""

from __future__ import annotations

from typing import Any, cast

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications
from api.routes.organization import router
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.models import RunId
from simulation.organization_models import SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS
from simulation.organization_ports import ORGANIZATION_CURSOR_PURPOSES
from simulation.runner import SimulationRunner
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
from tests.unit.test_organization_agency_runtime import _config
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

pytestmark = pytest.mark.unit


def test_exact_pins() -> None:
    assert METRIC_FAMILY_COUNT == 188
    assert len(all_metric_specifications()) == 188
    assert [spec.family_id.value for spec in all_metric_specifications()[146:148]] == [
        "organization_collective_agency",
        "organization_collective_implementation",
    ]
    assert SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS == (
        "organization-snapshot-v1",
        "organization-snapshot-v2",
        "organization-snapshot-v3",
    )
    assert ORGANIZATION_CURSOR_PURPOSES[-1] == "organization_collective_agency"
    assert len(ORGANIZATION_CURSOR_PURPOSES) == 6
    assert len(COMMAND_RULE_MATRIX) == 43
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_six_get_routes() -> None:
    routes = [
        route
        for route in router.routes
        if getattr(route, "path", "").startswith("/v1/simulations")
    ]
    assert len(routes) == 6
    assert all("GET" in getattr(route, "methods", set()) for route in routes)


@pytest.mark.asyncio
async def test_flags_off_has_no_agency_ledger_or_documents() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-agency-flags-off")
    ) as runner:
        result = await runner.run()
    assert result.organization_agency_ledgers == ()
    assert runner.export_organization_agency_ledgers() == ()


@pytest.mark.asyncio
async def test_flags_on_without_evidence_is_empty_not_fabricated() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-agency-empty")
    ) as runner:
        result = await runner.run()
    assert len(result.organization_agency_ledgers) == 1
    ledger = result.organization_agency_ledgers[0]
    assert cast(Any, ledger).concepts == ()
