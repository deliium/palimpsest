"""Physical control, subjective claims, and the objective frame stay separate."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.cognition.territorial import TerritorialClaimLedger
from api.observer_schemas import ObserverWorldStateOut
from api.simulation_manager import SimulationManager
from observer.contracts import (
    ObserverAgent,
    ObserverBodyMeasures,
    ObserverContractError,
    ObserverFrame,
    ObserverItem,
    ObserverLocation,
    ObserverPlaybackCursor,
    ObserverWorldState,
    observer_world_state_from_mapping,
)
from observer.project import project_physical_control
from observer.version import OBSERVER_PROTOCOL_VERSION
from simulation.inspection import (
    DetachedInspectionProjector,
    subjective_claims_document,
)
from tests.unit.test_identity_runtime import _runtime
from tests.unit.test_territorial_claims import _claim, _entity

_ROOT = Path(__file__).resolve().parents[2]
_LEAK_KEYS = (
    "relationship",
    "relationships",
    "territorial_claims",
    "spatial_control",
    "territory_owner",
    "controller",
)


def _measures() -> ObserverBodyMeasures:
    return ObserverBodyMeasures(
        health=100.0,
        hunger=0.0,
        thirst=0.0,
        fatigue=0.0,
        temperature=36.5,
    )


def _frame() -> ObserverFrame:
    world = ObserverWorldState(
        tick=1,
        revision=1,
        locations=(
            ObserverLocation(
                location_id="loc-1",
                name="camp",
                display_name="camp",
                neighbor_ids=(),
            ),
        ),
        agents=(
            ObserverAgent(
                entity_id="body-1",
                location_id="loc-1",
                life_status="alive",
                inventory_ids=(),
                measures=_measures(),
            ),
        ),
        items=(
            ObserverItem(
                item_id="item-1",
                name="ration",
                kind="food",
                holder_id="body-1",
            ),
        ),
    )
    return ObserverFrame(
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        cursor=ObserverPlaybackCursor(
            run_id="run-1",
            mode="live",
            tick=1,
            protocol_version=OBSERVER_PROTOCOL_VERSION,
        ),
        world=world,
    )


def test_leak_keys_cannot_sit_on_the_objective_world() -> None:
    for key in _LEAK_KEYS:
        with pytest.raises(ObserverContractError) as constructed:
            ObserverWorldState(tick=0, revision=0, **{key: "x"})
        assert constructed.value.reason_code == "objective_leak"
        assert constructed.value.field == key
        with pytest.raises(ObserverContractError) as parsed:
            observer_world_state_from_mapping({"tick": 0, "revision": 0, key: "x"})
        assert parsed.value.reason_code == "objective_leak"
        with pytest.raises(ValidationError):
            ObserverWorldStateOut.model_validate({"tick": 0, "revision": 0, key: "x"})


def test_physical_control_lists_presence_without_claim_ids() -> None:
    document = project_physical_control(_frame())
    assert document.schema_version == "physical-control-v1"
    assert document.authority == "physical_possession"
    assert document.locations[0].location_id == "loc-1"
    assert document.locations[0].agent_ids == ("body-1",)
    assert document.locations[0].item_ids == ("item-1",)
    rendered = repr(document)
    assert "claim_id" not in rendered


def test_subjective_claims_are_one_owner_and_empty_without_a_runtime() -> None:
    runtime, _reader = _runtime()
    exported = runtime.export_runtime_checkpoint()
    owner = runtime.agent_id
    ledger = TerritorialClaimLedger(
        owner_id=owner,
        claims=(_claim(owner, _entity("loc-1")),),
    )
    checkpoint = replace(exported, territorial_claims=ledger)
    selected = DetachedInspectionProjector().project_subjective_claims(checkpoint)
    assert selected.schema_version == "subjective-claims-v1"
    assert selected.layer == "subjective_claims"
    assert selected.owner_id == owner.value
    assert selected.heads[0].target_entity_id == "loc-1"
    other = subjective_claims_document("other-owner", checkpoint)
    assert other.heads == ()
    assert other.owner_id == "other-owner"
    absent = subjective_claims_document(owner.value, None)
    assert absent.heads == ()
    blank = replace(exported, territorial_claims=None)
    assert subjective_claims_document(owner.value, blank).heads == ()


def test_missing_in_process_runtime_is_not_a_checkpoint() -> None:
    manager = object.__new__(SimulationManager)
    manager._handles = {}
    assert manager.owner_runtime_checkpoint("run-1", "owner-1") is None


def test_stream_fixture_and_simulation_stay_free_of_claim_keys() -> None:
    fixture_path = (
        _ROOT / "clients/godot-observer/fixtures/smoke/reference_session.json"
    )
    fixture = json.loads(fixture_path.read_text())
    keys: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            keys.update(str(key) for key in value)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(fixture)
    assert keys.isdisjoint(_LEAK_KEYS)
    inspection = (_ROOT / "src/simulation/inspection.py").read_text()
    assert "import observer" not in inspection
    contract = (_ROOT / "pyproject.toml").read_text()
    assert 'forbidden_modules = [' in contract
    assert '"observer"' in contract
