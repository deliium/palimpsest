"""Observer contract validation and closed semantic types."""

from __future__ import annotations

import logging

import pytest

from observer.contracts import (
    ObserverAgent,
    ObserverBodyMeasures,
    ObserverContractError,
    ObserverEvent,
    ObserverManifest,
    ObserverWorldState,
)
from observer.version import (
    OBSERVER_PROTOCOL_VERSION,
    SEMANTIC_EVENT_TYPES,
    SEMANTIC_TYPE_BY_KIND,
)

pytestmark = pytest.mark.unit


def _measures() -> ObserverBodyMeasures:
    return ObserverBodyMeasures(
        health=100.0,
        hunger=0.0,
        thirst=0.0,
        fatigue=0.0,
        temperature=36.5,
    )


def _event(**overrides: object) -> ObserverEvent:
    payload: dict[str, object] = {
        "protocol_version": OBSERVER_PROTOCOL_VERSION,
        "type": "AGENT_MOVED",
        "domain_kind": "move",
        "event_id": "evt-1",
        "tick": 1,
        "sequence": 0,
    }
    payload.update(overrides)
    return ObserverEvent(**payload)  # type: ignore[arg-type]


def test_semantic_table_is_closed() -> None:
    assert tuple(SEMANTIC_TYPE_BY_KIND.values()) == SEMANTIC_EVENT_TYPES
    assert len(SEMANTIC_EVENT_TYPES) == 47
    assert SEMANTIC_EVENT_TYPES[-15:-11] == (
        "ARTIFACT_CREATED",
        "ARTIFACT_MODIFIED",
        "ARTIFACT_MOVED",
        "ARTIFACT_DESTROYED",
    )
    assert SEMANTIC_EVENT_TYPES[-11:-7] == (
        "ARTIFACT_COPIED",
        "ARTIFACT_ANNOTATED",
        "ARTIFACT_DAMAGED",
        "ARTIFACT_PARTIALLY_LOST",
    )
    assert SEMANTIC_EVENT_TYPES[-7:] == (
        "AGENT_CREATED",
        "AGENT_ENTERED_WORLD",
        "AGENT_INITIALIZED",
        "LIFECYCLE_STAGE_CHANGED",
        "KINSHIP_EDGE_RECORDED",
        "AGENT_FED",
        "AGENT_TRANSPORTED",
    )


def test_manifest_rejects_foreign_protocol_and_open_read_only() -> None:
    with pytest.raises(ObserverContractError) as foreign:
        ObserverManifest(
            protocol_version="observer-protocol-v0",
            layout_schema_version="observer-layout-v1",
            layout_id="reference-v1",
            layout_hash="abc",
            event_schema_version=5,
            projector_version="projector-v1",
            run_id="run-1",
        )
    assert foreign.value.reason_code == "unsupported_observer_protocol"
    with pytest.raises(ObserverContractError) as opened:
        ObserverManifest(
            protocol_version=OBSERVER_PROTOCOL_VERSION,
            layout_schema_version="observer-layout-v1",
            layout_id="reference-v1",
            layout_hash="abc",
            event_schema_version=5,
            projector_version="projector-v1",
            run_id="run-1",
            read_only=False,
        )
    assert opened.value.reason_code == "read_only_required"


def test_manifest_requires_run_id_and_fork_fields_together() -> None:
    root = ObserverManifest(
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        layout_schema_version="observer-layout-v1",
        layout_id="reference-v1",
        layout_hash="abc",
        event_schema_version=5,
        projector_version="projector-v1",
        run_id="run-root",
    )
    assert root.run_id == "run-root"
    assert root.parent_run_id is None
    fork = ObserverManifest(
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        layout_schema_version="observer-layout-v1",
        layout_id="reference-v1",
        layout_hash="abc",
        event_schema_version=5,
        projector_version="projector-v1",
        run_id="run-child",
        parent_run_id="run-root",
        fork_tick=3,
        intervention_summary="mortality_disabled:aaaaaaaaaaaa",
        branch_id="branch-1",
    )
    assert fork.branch_id == "branch-1"
    with pytest.raises(ObserverContractError) as missing_fork:
        ObserverManifest(
            protocol_version=OBSERVER_PROTOCOL_VERSION,
            layout_schema_version="observer-layout-v1",
            layout_id="reference-v1",
            layout_hash="abc",
            event_schema_version=5,
            projector_version="projector-v1",
            run_id="run-child",
            parent_run_id="run-root",
        )
    assert missing_fork.value.reason_code == "fork_tick_required"


def test_world_state_has_no_relationship_attribute() -> None:
    state = ObserverWorldState(tick=0, revision=0)
    assert "relationship" not in state.__dataclass_fields__
    assert not hasattr(state, "relationship")


def test_set_inventory_and_duplicate_ids_fail() -> None:
    with pytest.raises(ObserverContractError) as inventory:
        ObserverAgent(
            entity_id="body-1",
            location_id="loc-1",
            life_status="alive",
            inventory_ids={"item-1", "item-2"},  # type: ignore[arg-type]
            measures=_measures(),
        )
    assert inventory.value.reason_code == "unordered_inventory"
    agent = ObserverAgent(
        entity_id="body-1",
        location_id="loc-1",
        life_status="alive",
        inventory_ids=("item-1",),
        measures=_measures(),
    )
    with pytest.raises(ObserverContractError) as duplicate:
        ObserverWorldState(tick=1, revision=1, agents=(agent, agent))
    assert duplicate.value.reason_code == "duplicate_id"


def test_inverse_type_and_presentation_instruction_are_rejected() -> None:
    with pytest.raises(ObserverContractError) as inverse:
        _event(type="AGENT_UNDIED")
    assert inverse.value.reason_code == "presentation_instruction_forbidden"
    with pytest.raises(ObserverContractError) as pixels:
        _event(pixels=3)
    assert pixels.value.reason_code == "presentation_instruction_forbidden"
    assert pixels.value.field == "pixels"


def test_successful_construction_logs_metadata_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="observer.contracts"):
        event = _event()
    assert event.protocol_version == OBSERVER_PROTOCOL_VERSION
    assert any("protocol_version=" in message for message in caplog.messages)
    assert all("36.5" not in message for message in caplog.messages)
    text = " ".join(caplog.messages)
    assert "ERROR" not in text or "observer_contract_rejected" not in text
