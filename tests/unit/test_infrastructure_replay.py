"""Infrastructure write-pair events, schema selection, and semantic aliases."""

from __future__ import annotations

import pytest

from observer.version import SEMANTIC_EVENT_TYPES, SEMANTIC_TYPE_BY_KIND
from simulation.persistence import (
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
    checkpoint_schema_for_production,
)
from world.events import (
    EVENT_SCHEMA_REPLAY_V23,
    InfrastructureConstructed,
    InfrastructureDamaged,
    InfrastructureDecayed,
    InfrastructureDestroyed,
    InfrastructureRepaired,
    REPLAYABLE_EVENT_SCHEMA_VERSIONS,
    SUPPORTED_EVENT_SCHEMA_VERSIONS,
)
from world.identifiers import EntityId
from world.production import StructureKind

pytestmark = pytest.mark.unit


def _constructed(**overrides: object) -> InfrastructureConstructed:
    payload = {
        "asset_id": EntityId("infra-a"),
        "asset_kind": "bridge",
        "topology": "node",
        "status": "operational",
        "integrity": 1.0,
        "location_id": EntityId("loc-a"),
        "endpoint_location_id": None,
        "linked_structure_id": EntityId("struct-1"),
        "linked_project_id": EntityId("proj-1"),
        "tick": 3,
    }
    payload.update(overrides)
    return InfrastructureConstructed(**payload)  # type: ignore[arg-type]


def test_event_schema_v23_membership() -> None:
    assert EVENT_SCHEMA_REPLAY_V23 == 23
    assert EVENT_SCHEMA_REPLAY_V23 in SUPPORTED_EVENT_SCHEMA_VERSIONS
    assert EVENT_SCHEMA_REPLAY_V23 in REPLAYABLE_EVENT_SCHEMA_VERSIONS


def test_infrastructure_events_validate() -> None:
    built = _constructed()
    assert built.kind == "infrastructure_constructed"
    repaired = InfrastructureRepaired(
        EntityId("infra-a"),
        "bridge",
        "node",
        "operational",
        0.9,
        EntityId("loc-a"),
        None,
        EntityId("struct-1"),
        EntityId("proj-1"),
        4,
    )
    damaged = InfrastructureDamaged(
        EntityId("infra-a"),
        "bridge",
        "node",
        "damaged",
        0.2,
        EntityId("loc-a"),
        None,
        EntityId("struct-1"),
        EntityId("proj-1"),
        5,
    )
    decayed = InfrastructureDecayed(
        EntityId("infra-a"),
        "bridge",
        "node",
        "damaged",
        0.19,
        EntityId("loc-a"),
        None,
        EntityId("struct-1"),
        EntityId("proj-1"),
        6,
    )
    destroyed = InfrastructureDestroyed(
        EntityId("infra-a"),
        "bridge",
        "node",
        "destroyed",
        0.0,
        EntityId("loc-a"),
        None,
        EntityId("struct-1"),
        EntityId("proj-1"),
        7,
    )
    assert repaired.kind == "infrastructure_repaired"
    assert damaged.kind == "infrastructure_damaged"
    assert decayed.kind == "infrastructure_decayed"
    assert destroyed.kind == "infrastructure_destroyed"


def test_semantic_aliases_and_pin() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert SEMANTIC_TYPE_BY_KIND["infrastructure_constructed"] == "STRUCTURE_BUILT"
    assert SEMANTIC_TYPE_BY_KIND["infrastructure_repaired"] == "STRUCTURE_REPAIRED"
    assert SEMANTIC_TYPE_BY_KIND["infrastructure_damaged"] == "PUBLIC_GOOD_OPPOSED"
    assert SEMANTIC_TYPE_BY_KIND["infrastructure_decayed"] == "ARTIFACT_DAMAGED"
    assert SEMANTIC_TYPE_BY_KIND["infrastructure_destroyed"] == "ARTIFACT_DESTROYED"
    assert "INFRASTRUCTURE_CONSTRUCTED" not in SEMANTIC_EVENT_TYPES


def test_schema_selection_matrix() -> None:
    assert checkpoint_schema_for_production(
        production_active=False,
        infrastructure_networks_active=True,
        collective_projects_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V23, "v21")
    # Infrastructure outranks cultural contact.
    assert checkpoint_schema_for_production(
        production_active=False,
        infrastructure_networks_active=True,
        cultural_contact_active=True,
        collective_projects_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V23, "v21")
    assert "v21" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS


def test_structure_kind_gate_symbols_exist() -> None:
    assert StructureKind.ROAD.value == "road"
    assert StructureKind.IRRIGATION.value == "irrigation"
    assert StructureKind.TRADE_POST.value == "trade_post"
