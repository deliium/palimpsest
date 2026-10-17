"""Experiment BA registers contact arms off the V1 gate."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import pytest

from experiments.catalog import OFF_GATE_MATRIX_EXPERIMENT_IDS
from experiments.collectors import CollectorMetricDocument
from experiments.cultural_contact_scenario import (
    cultural_contact_arbiter,
    cultural_contact_scenario,
)
from simulation.runner_models import RUNNER_SCHEMA_VERSION_V4, RUNNER_SCHEMA_VERSION_V45
from world.events import WorldEvent


def test_ba_is_off_gate_and_has_six_arms() -> None:
    definition = cultural_contact_scenario()
    assert definition.experiment_id == "cultural_contact@1"
    assert "cultural_contact@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert len(definition.conditions) == 6
    assert {item.condition_id for item in definition.conditions} == {
        "ba-channel-off",
        "ba-isolated",
        "ba-contact-trade",
        "ba-contact-teaching",
        "ba-contact-conflict-cooperation",
        "ba-contact-kinship",
    }


def test_ba_schemas_select_v45_only_with_contact() -> None:
    definition = cultural_contact_scenario()
    by_id = {item.condition_id: item.runner_config for item in definition.conditions}
    assert by_id["ba-channel-off"].schema_version == RUNNER_SCHEMA_VERSION_V4
    assert by_id["ba-channel-off"].cultural_contact is None
    for condition_id in (
        "ba-isolated",
        "ba-contact-trade",
        "ba-contact-teaching",
        "ba-contact-conflict-cooperation",
        "ba-contact-kinship",
    ):
        config = by_id[condition_id]
        assert config.schema_version == RUNNER_SCHEMA_VERSION_V45
        assert config.cultural_contact is not None
        assert config.regions_migration is not None


def test_ba_isolated_has_no_cross_region_moves() -> None:
    definition = cultural_contact_scenario()
    config = next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == "ba-isolated"
    )
    arbiter = cultural_contact_arbiter("ba-isolated", config)
    assert arbiter is not None
    # Isolated keeps local talk only; no milestone targets the southern region.
    assert not any(
        getattr(milestone.build_command(), "kind", "") == "move"
        for milestone in arbiter._milestones
    )


def test_ba_channel_off_has_no_arbiter() -> None:
    definition = cultural_contact_scenario()
    config = definition.conditions[0].runner_config
    assert cultural_contact_arbiter("ba-channel-off", config) is None


@pytest.mark.asyncio
async def test_contact_arm_records_contact_and_isolated_does_not() -> None:
    from experiments.coordinator import materialize_assignments
    from experiments.cultural_contact_scenario import (
        assert_cultural_contact_structure,
    )
    from experiments.matrix_runner import run_one_assignment

    definition = cultural_contact_scenario(seed=29, max_ticks=8)
    assignments = {
        item.condition_id: item for item in materialize_assignments(definition)
    }
    contact_arm = await run_one_assignment(assignments["ba-contact-trade"])
    isolated_arm = await run_one_assignment(assignments["ba-isolated"])
    contact_events = contact_arm.committed_events
    isolated_events = isolated_arm.committed_events
    assert contact_events is not None
    assert isolated_events is not None
    contact_facts = assert_cultural_contact_structure(
        "ba-contact-trade", cast(Sequence[WorldEvent], contact_events)
    )
    assert contact_facts["contact_event_count"] >= 1
    isolated_facts = assert_cultural_contact_structure(
        "ba-isolated", cast(Sequence[WorldEvent], isolated_events)
    )
    assert isolated_facts["contact_event_count"] == 0
    catalog = next(
        item
        for item in contact_arm.metrics
        if isinstance(item, CollectorMetricDocument)
        and item.family == "catalog_metrics"
    )
    fields = dict(catalog.fields)
    assert fields["society_contact_availability"] in {"present", "partial"}
