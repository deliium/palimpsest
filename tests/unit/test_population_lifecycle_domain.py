"""Unit tests for population lifecycle domain types."""

from __future__ import annotations

import logging

import pytest

from world.identifiers import EntityId
from world.lifecycle import (
    AgentLifecycleRecord,
    DependencyStatus,
    LifecycleStageId,
    OriginProvenance,
    chronological_age,
    require_lifecycle_stage_id,
)

_LOG = logging.getLogger("tests.population_lifecycle_domain")


def test_lifecycle_stage_id_and_enums() -> None:
    _LOG.debug("case_id=lifecycle_stage_id_and_enums")
    stage = LifecycleStageId("infant")
    assert stage.value == "infant"
    assert require_lifecycle_stage_id("juvenile") == LifecycleStageId("juvenile")
    assert require_lifecycle_stage_id(stage) is stage
    assert list(DependencyStatus) == [
        DependencyStatus.DEPENDENT,
        DependencyStatus.INDEPENDENT,
    ]
    assert list(OriginProvenance) == [
        OriginProvenance.BOOTSTRAP,
        OriginProvenance.DEMOGRAPHIC_POLICY,
        OriginProvenance.EXTERNAL_ENTRY,
    ]


def test_agent_lifecycle_record_construction() -> None:
    _LOG.debug("case_id=agent_lifecycle_record_construction")
    record = AgentLifecycleRecord(
        body_id=EntityId("body-1"),
        agent_id="agent-1",
        entry_tick=0,
        stage=LifecycleStageId("infant"),
        dependency_status=DependencyStatus.DEPENDENT,
        generation_index=0,
        cohort_id="cohort-bootstrap",
        provenance=OriginProvenance.BOOTSTRAP,
    )
    assert record.body_id == EntityId("body-1")
    assert record.entry_tick == 0
    assert record.generation_index == 0
    assert not hasattr(record, "sex")
    assert not hasattr(record, "parent_id")
    assert "chronological_age" not in record.__dataclass_fields__


@pytest.mark.parametrize(
    ("entry_tick", "current_tick", "expected"),
    [
        (0, 0, 0),
        (0, 5, 5),
        (3, 3, 0),
        (3, 10, 7),
    ],
)
def test_chronological_age_derivation(
    entry_tick: int, current_tick: int, expected: int
) -> None:
    _LOG.debug(
        "case_id=chronological_age entry=%s current=%s",
        entry_tick,
        current_tick,
    )
    assert (
        chronological_age(entry_tick=entry_tick, current_tick=current_tick)
        == expected
    )


def test_chronological_age_rejects_tick_order() -> None:
    _LOG.debug("case_id=chronological_age_tick_order")
    with pytest.raises(ValueError, match="lifecycle_age_tick_order"):
        chronological_age(entry_tick=5, current_tick=4)


def test_agent_lifecycle_record_rejects_invalid_fields() -> None:
    _LOG.debug("case_id=agent_lifecycle_record_invalid")
    with pytest.raises(TypeError, match="body_id"):
        AgentLifecycleRecord(
            body_id="body-1",  # type: ignore[arg-type]
            agent_id="agent-1",
            entry_tick=0,
            stage=LifecycleStageId("infant"),
            dependency_status=DependencyStatus.DEPENDENT,
            generation_index=0,
            cohort_id="cohort-a",
            provenance=OriginProvenance.BOOTSTRAP,
        )
    with pytest.raises(ValueError, match="entry_tick"):
        AgentLifecycleRecord(
            body_id=EntityId("body-1"),
            agent_id="agent-1",
            entry_tick=-1,
            stage=LifecycleStageId("infant"),
            dependency_status=DependencyStatus.DEPENDENT,
            generation_index=0,
            cohort_id="cohort-a",
            provenance=OriginProvenance.BOOTSTRAP,
        )
