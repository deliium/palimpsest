"""Observer manifest/run carry run_id and optional branch lineage fields."""

from __future__ import annotations

import pytest

from observer.contracts import ObserverManifest
from observer.layout import load_layout
from observer.sources import LiveObserverSource
from observer.version import OBSERVER_PROTOCOL_VERSION
from simulation.branching import (
    BranchLineage,
    InMemoryBranchLineageRepository,
    ResearchInterventionKind,
)
from simulation.models import RunId
from simulation.observer_facts import ObjectiveScene
from simulation.persistence import EVENT_SCHEMA_VERSION, PROJECTOR_VERSION
from tests.simulation_helpers import alive_body, make_location, make_weather

pytestmark = pytest.mark.unit


def _scene(*, run_id: str = "run-root") -> ObjectiveScene:
    body = alive_body()
    return ObjectiveScene(
        run_id=run_id,
        world_id="world-1",
        tick=0,
        revision=0,
        locations=(make_location(),),
        bodies=(body,),
        items=(),
        resources=(),
        weather=(make_weather(),),
        registrations=(),
    )


def test_live_source_manifest_always_includes_run_id() -> None:
    layout = load_layout("reference-v1")
    source = LiveObserverSource(
        scene=_scene(),
        events=(),
        layout=layout,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
    )
    manifest = source.manifest()
    assert type(manifest) is ObserverManifest
    assert manifest.run_id == "run-root"
    assert manifest.parent_run_id is None
    assert manifest.fork_tick is None
    assert manifest.branch_id is None
    assert manifest.protocol_version == OBSERVER_PROTOCOL_VERSION


def test_live_source_manifest_exposes_fork_lineage() -> None:
    layout = load_layout("reference-v1")
    source = LiveObserverSource(
        scene=_scene(run_id="run-child"),
        events=(),
        layout=layout,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        parent_run_id="run-root",
        fork_tick=4,
        intervention_summary="mortality_disabled:aaaaaaaaaaaa",
        branch_id="branch-1",
    )
    manifest = source.manifest()
    assert manifest.run_id == "run-child"
    assert manifest.parent_run_id == "run-root"
    assert manifest.fork_tick == 4
    assert manifest.branch_id == "branch-1"


@pytest.mark.asyncio
async def test_lineage_repo_round_trip_for_observer_fields() -> None:
    repo = InMemoryBranchLineageRepository()
    lineage = BranchLineage(
        child_run_id=RunId("run-child"),
        parent_run_id=RunId("run-root"),
        fork_tick=4,
        intervention_kind=ResearchInterventionKind.MORTALITY_DISABLED,
        intervention_fingerprint="c" * 64,
        intervention_canonical={"kind": "mortality_disabled"},
        branch_id="branch-1",
        created_as_of_parent_head=9,
    )
    await repo.put_lineage(lineage)
    loaded = await repo.get_lineage(child_run_id=RunId("run-child"))
    assert loaded is not None
    assert loaded.fork_tick == 4
    root = await repo.get_lineage(child_run_id=RunId("run-root"))
    assert root is None
