# mypy: ignore-errors
"""In-process infrastructure_networks E2E: construct → effect → lifecycle → surfaces.

Unit lane only. Never requires PostgreSQL, Docker, network, or an external LLM.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition.collective_projects import propose_collective_project_command
from agents.models import AgentId
from analysis.infrastructure_metrics import (
    compute_infrastructure_network_structure,
    harvest_infrastructure_networks_analysis,
)
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.specifications import MetricFamilyId
from api.dependencies import get_infrastructure_networks_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.infrastructure_networks_cursor import InfrastructureNetworksCursorCodec
from api.routes.infrastructure_networks import router
from experiments.infrastructure_publication import (
    publish_infrastructure_networks_snapshot,
)
from infrastructure.settings import Settings
from persistence.infrastructure_filesystem import (
    create_infrastructure_networks_publisher,
    create_infrastructure_networks_reader,
)
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    make_item,
    weather_for_locations,
)
from world._infrastructure import (
    decay_infrastructure,
    effective_body_capacity,
    effective_resource_regen_delta,
    effective_travel_duration,
)
from world._skills import (
    ObjectiveSkillLedger,
    SkillDomain,
    default_objective_skill_policy,
)
from world.actions import (
    ContributeCollectiveProject,
    Repair,
    StartCollectiveProject,
    Wait,
)
from world.identifiers import EntityId, RecipeId, WorldId, WorldRevision
from world.infrastructure import InfrastructureKind, InfrastructureStatus
from world.models import LifeStatus, non_lethal_physical_rules
from world.production import StructureKind, example_production_catalog
from world.values import ItemKind

pytestmark = pytest.mark.unit

RUN = "run-infra-e2e"
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
AGENT = AgentId("agent-1")
BODY = EntityId("body-1")
LOC_A = EntityId("loc-a")
LOC_B = EntityId("loc-b")
PATHS = (
    f"/v1/simulations/{RUN}/infrastructure-networks",
    f"/v1/simulations/{RUN}/infrastructure-networks/assets",
    f"/v1/simulations/{RUN}/infrastructure-networks/edges",
    f"/v1/simulations/{RUN}/infrastructure-networks/condition",
    f"/v1/simulations/{RUN}/infrastructure-networks/effects",
    f"/v1/simulations/{RUN}/infrastructure-networks/maintenance",
)


def _board(code: str) -> SimpleNamespace:
    return SimpleNamespace(
        goals=(
            SimpleNamespace(
                goal_id="g1",
                outcome=SimpleNamespace(outcome_code=code),
            ),
        ),
        foci_ids=("g1",),
    )


def _material(entity_id: str, name: str, holder: str) -> object:
    return make_item(
        entity_id,
        name=name,
        kind=ItemKind.MATERIAL,
        location_id=None,
        holder_id=holder,
    )


def _skilled(*entity_ids: str) -> dict[str, object]:
    ids = tuple(EntityId(item) for item in entity_ids)
    ledger = ObjectiveSkillLedger.bootstrap(ids).apply_summed_deltas(
        {entity_id: {SkillDomain.BUILDING: 1.0} for entity_id in ids}
    )
    return {
        "skill_policy": default_objective_skill_policy(),
        "skill_entity_ids": ids,
        "skill_ledger": ledger,
    }


def _bootstrap(
    items: tuple[object, ...], inventory: tuple[EntityId, ...]
) -> WorldBootstrap:
    locations = connected_locations(("loc-a", "Camp"), ("loc-b", "Field"))
    body = alive_body(
        "body-1",
        location_id="loc-a",
        inventory=inventory,
        carry_capacity=32,
    )
    return WorldBootstrap(
        world_id=WorldId("world-infra-e2e"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(body,),
        items=items,
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(AGENT, BODY),),
    )


def _engine(items: tuple[object, ...], inventory: tuple[EntityId, ...]) -> WorldEngine:
    return WorldEngine(
        config=SimulationRunConfig(
            seed=41, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=_bootstrap(items, inventory),
        production_catalog=example_production_catalog(),
        collective_projects_active=True,
        collective_projects_idle_ticks=64,
        infrastructure_networks_active=True,
        public_goods_active=False,
        **_skilled("body-1"),
    )


def _step(engine: WorldEngine, command: object) -> object:
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(token=batch.token, agent_id=AGENT, command=command),)
    )
    assert result is not None
    return result


def _complete_project(
    engine: WorldEngine,
    *,
    start: StartCollectiveProject,
    material_ids: tuple[EntityId, ...],
    labor: int,
) -> EntityId:
    _step(engine, start)
    projects = engine._snapshot.world.state.collective_projects
    project_id = next(
        project.project_id
        for project in projects.values()
        if project.kind.value == start.project_kind and project.status.value == "open"
    )
    for item_id in material_ids:
        _step(engine, ContributeCollectiveProject(project_id, item_id))
    for _ in range(labor):
        _step(engine, ContributeCollectiveProject(project_id))
    finished = engine._snapshot.world.state.collective_projects[project_id]
    assert finished.status.value == "completed"
    return project_id


def _assets(engine: WorldEngine) -> dict[EntityId, object]:
    infra = engine._snapshot.world.state.infrastructure
    assert infra is not None
    return dict(infra)


def test_construct_effects_lifecycle_publish_and_six_routes(tmp_path: Path) -> None:
    stones = tuple(
        _material(f"stone-{index}", "stone", "body-1") for index in range(1, 6)
    )
    woods = tuple(_material(f"wood-{index}", "wood", "body-1") for index in range(1, 5))
    repair_mat = _material("repair-mat", "wood", "body-1")
    items = (*stones, *woods, repair_mat)
    inventory = tuple(item.entity_id for item in items)
    engine = _engine(items, inventory)

    # Cognition proposes road start with adjacent target_location_id.
    batch = engine.observe()
    observation = next(
        item for item in batch.observations if item.observer_id == BODY
    )
    proposed = propose_collective_project_command(
        Wait(),
        observation,
        _board("collective_project:start:road"),
        channel_on=True,
        owner_id=AGENT,
    )
    assert isinstance(proposed, StartCollectiveProject)
    assert proposed.project_kind == "road"
    assert proposed.target_location_id == LOC_B

    _complete_project(
        engine,
        start=proposed,
        material_ids=(EntityId("stone-1"), EntityId("stone-2"), EntityId("stone-3")),
        labor=5,
    )
    _complete_project(
        engine,
        start=StartCollectiveProject("large_shelter"),
        material_ids=(EntityId("wood-1"), EntityId("wood-2"), EntityId("wood-3")),
        labor=5,
    )
    _complete_project(
        engine,
        start=StartCollectiveProject("irrigation"),
        material_ids=(EntityId("stone-4"), EntityId("stone-5")),
        labor=4,
    )

    assets = _assets(engine)
    by_kind = {asset.kind: asset for asset in assets.values()}
    assert InfrastructureKind.ROAD in by_kind
    assert InfrastructureKind.LARGE_SHELTER in by_kind
    assert InfrastructureKind.IRRIGATION in by_kind
    road = by_kind[InfrastructureKind.ROAD]
    assert road.endpoint_location_id == LOC_B
    assert road.status is InfrastructureStatus.OPERATIONAL
    assert any(
        structure.kind is StructureKind.ROAD
        for structure in engine._snapshot.world.state.structures.values()
    )

    # Travel / capacity / regen effects from completed assets.
    assert (
        effective_travel_duration(
            assets,
            origin_id=LOC_A,
            destination_id=LOC_B,
            base_duration=3,
        )
        == 2
    )
    assert (
        effective_body_capacity(assets, location_id=LOC_A, base_capacity=4) == 6
    )
    assert effective_resource_regen_delta(assets, location_id=LOC_A) == pytest.approx(
        0.05
    )

    # Damage structure + infra; Repair road without public_goods restores it.
    from dataclasses import replace

    from simulation.lifecycle import ActionResolutionStatus
    from world._infrastructure import sync_infrastructure_with_structures
    from world._state import World, rebuild_world_state

    state = engine._snapshot.world.state
    assert road.linked_structure_id is not None
    structure = state.structures[road.linked_structure_id]
    structures = dict(state.structures)
    structures[structure.entity_id] = replace(structure, integrity=0.5)
    damaged = sync_infrastructure_with_structures(
        rebuild_world_state(state, structures=structures)
    )
    before_repair = damaged.infrastructure[road.asset_id].integrity
    assert before_repair < 1.0
    engine._snapshot = replace(
        engine._snapshot,
        world=World(engine._snapshot.world.world_id, damaged),
    )
    result = _step(
        engine,
        Repair(RecipeId("repair_shelter"), road.linked_structure_id),
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    repaired_asset = engine._snapshot.world.state.infrastructure[road.asset_id]
    assert repaired_asset.integrity > before_repair
    assert engine._public_goods_active is False

    # Destroy one asset (irrigation) via decay without auto-maintain.
    current = engine._snapshot.world.state
    irrigation = by_kind[InfrastructureKind.IRRIGATION]
    for tick in range(200, 400):
        current, _ = decay_infrastructure(current, tick=tick)
        if (
            current.infrastructure[irrigation.asset_id].status
            is InfrastructureStatus.DESTROYED
        ):
            break
    destroyed = current.infrastructure[irrigation.asset_id]
    assert destroyed.status is InfrastructureStatus.DESTROYED
    assert destroyed.integrity == 0.0
    assert irrigation.asset_id in current.infrastructure

    # Metrics emit only when analysis is supplied.
    analysis = harvest_infrastructure_networks_analysis(
        tuple(current.infrastructure.values()),
        window_tick=64,
    )
    structure = compute_infrastructure_network_structure(
        analysis, run_id=RUN, input_revision="rev-infra-e2e"
    )
    assert structure.values["asset_count"] >= 3
    assert "score" not in structure.values
    with_gate = assemble_metric_documents(
        MetricComputationInputs(
            run_id=RUN,
            input_revision="rev-infra-e2e",
            window_end=64,
            infrastructure_networks_analysis=analysis,
        )
    )
    families = {doc.metric_family for doc in with_gate.documents}
    assert MetricFamilyId.INFRASTRUCTURE_NETWORK_STRUCTURE.value in families
    without = assemble_metric_documents(
        MetricComputationInputs(
            run_id=RUN,
            input_revision="rev-infra-e2e",
            window_end=64,
        )
    )
    absent = {doc.metric_family for doc in without.documents}
    assert MetricFamilyId.INFRASTRUCTURE_NETWORK_STRUCTURE.value not in absent

    # Dual-gate publish + all six routes; no score fields.
    runner = SimpleNamespace(
        stop_reason=SimpleNamespace(value="max_ticks"),
        status="completed",
        infrastructure_assets=tuple(current.infrastructure.values()),
        window_end=64,
    )
    root = tmp_path / "store"
    publisher = create_infrastructure_networks_publisher(root)
    receipt = publish_infrastructure_networks_snapshot(
        runner, publisher, run_id=RUN, analysis=analysis
    )
    assert receipt.status == "published"
    assert receipt.publication_id is not None

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_infrastructure_networks_reader(root)
    app.dependency_overrides[get_infrastructure_networks_reader] = lambda: reader
    app.state.infrastructure_networks_reader = reader
    app.state.infrastructure_networks_cursor_codec = InfrastructureNetworksCursorCodec(
        b"k" * 32, now=lambda: 0.0
    )

    async def call_routes() -> list[httpx.Response]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return [await client.get(path, headers=HEADERS) for path in PATHS]

    responses = asyncio.run(call_routes())
    assert [response.status_code for response in responses] == [200] * 6
    for response in responses:
        text = response.text
        assert "score" not in text
        assert "civilization_score" not in text
        assert "infrastructure_score" not in text


def test_dual_gate_unset_reader_is_503() -> None:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_infrastructure_networks_reader] = lambda: None
    app.state.infrastructure_networks_reader = None
    app.state.infrastructure_networks_cursor_codec = None

    async def call() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(PATHS[0], headers=HEADERS)

    response = asyncio.run(call())
    assert response.status_code == 503
    assert response.json()["detail"] == "infrastructure_networks_disabled"


def test_publish_failure_leaves_scientific_status_unchanged() -> None:
    class _Boom:
        def publish(self, snapshot: object) -> None:
            raise RuntimeError("storage")

    analysis = harvest_infrastructure_networks_analysis((), window_tick=0)
    runner = SimpleNamespace(
        stop_reason=SimpleNamespace(value="max_ticks"),
        status="completed",
        infrastructure_assets=(),
        window_end=0,
    )
    before = (runner.stop_reason.value, runner.status, runner.infrastructure_assets)
    receipt = publish_infrastructure_networks_snapshot(
        runner, _Boom(), run_id=RUN, analysis=analysis
    )
    assert receipt.status == "failed"
    assert (
        runner.stop_reason.value,
        runner.status,
        runner.infrastructure_assets,
    ) == before


def test_cognition_road_target_requires_adjacent_exit() -> None:
    observation = SimpleNamespace(
        self_body=SimpleNamespace(life_status=LifeStatus.ALIVE),
        collective_projects=(),
        structures=(),
        items=(),
        exits=(),
    )
    prior = Wait()
    assert (
        propose_collective_project_command(
            prior,
            observation,
            _board("collective_project:start:road"),
            channel_on=True,
            owner_id=AGENT,
        )
        is prior
    )
