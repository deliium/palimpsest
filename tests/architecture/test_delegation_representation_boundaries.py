"""V4-09 ownership boundary: deepen organizations without a new schema."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    SimulationRunner,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-representation-boundary",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-representation-boundary"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=2,
    )


def _owned_names() -> tuple[str, ...]:
    return tuple(
        name
        for name in V4_CAPABILITY_FLAGS
        if V4CapabilityFlags(**{name: True}).owned_enabled_names() == (name,)
    )


def test_v4_09_deepens_organizations_without_new_schema() -> None:
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert set(_owned_names()) == {
        "organizations",
        "formal_rules",
        "legal_disputes",
        "diplomacy",
        "organized_conflict",
        "infrastructure_networks",
        "supply_chains",
        "markets_credit",
    }

    organizations = V4_CONTEXT_BY_ID[V4ContextId.ORGANIZATIONS]
    diplomacy = V4_CONTEXT_BY_ID[V4ContextId.DIPLOMACY]
    assert organizations.authority is V4Authority.OWNER_SCOPED
    assert V4ContextId.ORGANIZATIONS in diplomacy.prerequisite_contexts
    assert V4CapabilityFlags(organized_conflict=True).owned_enabled_names() == (
        "organized_conflict",
    )

    representation_contexts = {
        context_id
        for context_id, spec in V4_CONTEXT_BY_ID.items()
        if context_id.value == "representation"
    }
    assert representation_contexts == set()


def test_no_runner_config_v57_literal_in_source() -> None:
    offenders = []
    for path in sorted(_SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if "runner-config-v57" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(_SRC)))
    assert offenders == []


@pytest.mark.asyncio
async def test_organized_conflict_requires_diplomacy_prerequisite() -> None:
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(organized_conflict=True),
    )

    with pytest.raises(RunnerConstructionError) as excinfo:
        await SimulationRunner.from_config(
            config, run_id=RunId("run-v4-representation-gate")
        )

    assert excinfo.value.code is RunnerConstructionErrorCode.V4_PREREQUISITE_MISSING
    assert excinfo.value.stage == "v4_capability_flags"


def test_no_representation_oracle_registry_or_command_path() -> None:
    import ast

    paths = (
        _SRC / "agents" / "cognition" / "delegation_representation.py",
        _SRC / "agents" / "cognition" / "delegation_representation_communication.py",
    )
    forbidden = {
        "TruthEngine",
        "LegitimacyOracle",
        "RepresentationAuthority",
        "Verifier",
        "Authenticator",
        "Winner",
        "AgentCommand",
        "ActionSubmission",
        "WorldEngine",
        "RepresentativeRegistry",
        "CoalitionRegistry",
        "SettlementRegistry",
    }
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            node.id if isinstance(node, ast.Name) else node.attr
            for node in ast.walk(tree)
            if isinstance(node, (ast.Name, ast.Attribute))
        }
        assert names & forbidden == set(), path.name


def test_ledger_module_imports_no_world_or_outer_package() -> None:
    import ast

    path = _SRC / "agents" / "cognition" / "delegation_representation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
    assert imported & {"world", "simulation", "persistence", "api", "analysis"} == set()


def test_no_forbidden_representation_field_names() -> None:
    from dataclasses import fields

    from agents.cognition import (
        RepresentationConflict,
        RepresentationLedger,
        RepresentationMandate,
        RepresentationPosition,
        RepresentationRevocation,
        RepresentationStandingSummary,
    )

    forbidden = {
        "truth",
        "verified",
        "legitimate",
        "authority",
        "permission",
        "allowed",
        "winner",
        "proxy",
        "mandate_valid",
    }
    for model in (
        RepresentationMandate,
        RepresentationPosition,
        RepresentationRevocation,
        RepresentationConflict,
        RepresentationLedger,
        RepresentationStandingSummary,
    ):
        assert {field.name for field in fields(model)} & forbidden == set()


def test_six_routes_and_six_cursor_purposes() -> None:
    from typing import Any, cast

    from api.routes.delegation_representation import router
    from simulation.delegation_representation_ports import (
        DELEGATION_REPRESENTATION_CURSOR_PURPOSES,
    )

    routes: list[Any] = []
    for route in router.routes:
        if getattr(route, "methods", None):
            routes.append(cast(Any, route))
    assert len(routes) == 6
    assert all(route.methods == {"GET"} for route in routes)
    assert DELEGATION_REPRESENTATION_CURSOR_PURPOSES == (
        "summary",
        "mandates",
        "mandate",
        "positions",
        "revocations",
        "lineage",
    )


def test_snapshot_store_and_catalog_pins() -> None:
    from analysis.specifications import (
        METRIC_FAMILY_COUNT,
        MetricFamilyId,
        all_metric_specifications,
    )
    from persistence.delegation_representation_filesystem import (
        DELEGATION_REPRESENTATION_STORE_SCHEMA,
    )
    from simulation.compatibility import ALEMBIC_HEAD_REVISION
    from simulation.delegation_representation_models import (
        DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA,
    )
    from world.events import EVENT_SCHEMA_REPLAY_V22

    assert METRIC_FAMILY_COUNT == 216
    assert DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA == (
        "delegation-representation-snapshot-v1"
    )
    assert DELEGATION_REPRESENTATION_STORE_SCHEMA == (
        "delegation-representation-store-v1"
    )
    assert [spec.family_id for spec in all_metric_specifications()[157:160]] == [
        MetricFamilyId.REPRESENTATION_MANDATE_STRUCTURE,
        MetricFamilyId.REPRESENTATION_RECOGNITION_SUPPORT,
        MetricFamilyId.REPRESENTATION_SCOPE_ALIGNMENT,
    ]
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert not list((_SRC.parent / "alembic" / "versions").glob("0018_*.py"))
